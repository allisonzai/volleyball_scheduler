from __future__ import annotations
"""
Core scheduling service for volleyball games.

State machine:
  waiting list -> PENDING_CONFIRMATION -> CONFIRMED (playing) or DECLINED/TIMED_OUT -> end of waiting list
"""
import asyncio
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.config import settings
from app.models.game import Game, GameStatus
from app.models.game_slot import GameSlot, SlotStatus
from app.models.waiting_list import WaitingList
from app.services.notifications import notify_player

logger = logging.getLogger(__name__)

# In-memory map of (player_id, game_id) -> asyncio.Task for confirmation timeouts
_timeout_tasks: dict = {}

# Captured main event loop — set at app startup via set_event_loop()
_main_loop: Optional[asyncio.AbstractEventLoop] = None


def set_event_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _main_loop
    _main_loop = loop

# SSE broadcast queue — any listener can subscribe
_sse_subscribers: list[asyncio.Queue] = []


def broadcast_update(event: str) -> None:
    """Push a state change event to all SSE listeners."""
    for q in _sse_subscribers:
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            pass


def subscribe_sse() -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue(maxsize=100)
    _sse_subscribers.append(q)
    return q


def unsubscribe_sse(q: asyncio.Queue) -> None:
    try:
        _sse_subscribers.remove(q)
    except ValueError:
        pass


# ---------------------------------------------------------------------------
# Waiting list helpers
# ---------------------------------------------------------------------------

def _next_signup_number(db: Session) -> int:
    """Return the next globally incrementing signup number."""
    max_num = db.query(func.max(WaitingList.signup_number)).scalar()
    return (max_num or 0) + 1


def _resequence(db: Session) -> None:
    """Compact queue positions to 1, 2, 3, … in current order."""
    entries = db.query(WaitingList).order_by(WaitingList.position).all()
    for i, entry in enumerate(entries, start=1):
        entry.position = i
    db.flush()


def _append_to_queue(db: Session, player_id: int) -> WaitingList:
    """Add player to end of waiting list (or re-add after game)."""
    existing = db.query(WaitingList).filter(WaitingList.player_id == player_id).first()
    if existing:
        return existing  # already in queue — do not double-add

    max_pos = db.query(func.max(WaitingList.position)).scalar() or 0
    entry = WaitingList(
        player_id=player_id,
        signup_number=_next_signup_number(db),
        position=max_pos + 1,
    )
    db.add(entry)
    db.flush()
    return entry


def _prepend_to_queue(db: Session, player_id: int) -> WaitingList:
    """Add player to front of waiting list (defer case)."""
    existing = db.query(WaitingList).filter(WaitingList.player_id == player_id).first()
    if existing:
        existing.position = 0
        _resequence(db)
        return existing

    # Shift everyone else down
    db.query(WaitingList).update({WaitingList.position: WaitingList.position + 1})
    entry = WaitingList(
        player_id=player_id,
        signup_number=_next_signup_number(db),
        position=1,
    )
    db.add(entry)
    db.flush()
    _resequence(db)
    return entry


def _remove_from_queue(db: Session, player_id: int) -> None:
    entry = db.query(WaitingList).filter(WaitingList.player_id == player_id).first()
    if entry:
        db.delete(entry)
        db.flush()
        _resequence(db)


def get_queue(db: Session) -> list[WaitingList]:
    return db.query(WaitingList).order_by(WaitingList.position).all()


# ---------------------------------------------------------------------------
# Game helpers
# ---------------------------------------------------------------------------

def _confirmed_count(game: Game) -> int:
    return sum(1 for s in game.slots if s.status == SlotStatus.CONFIRMED)


def _pending_count(game: Game) -> int:
    return sum(1 for s in game.slots if s.status == SlotStatus.PENDING_CONFIRMATION)


def _next_slot_position(game: Game) -> int:
    used = {s.position for s in game.slots}
    for i in range(1, game.max_players + 1):
        if i not in used:
            return i
    return len(game.slots) + 1


# ---------------------------------------------------------------------------
# Timeout task
# ---------------------------------------------------------------------------

def _cancel_timeout(player_id: int, game_id: int) -> None:
    key = (player_id, game_id)
    future = _timeout_tasks.pop(key, None)
    if future and not future.done():
        future.cancel()


def _schedule_timeout(player_id: int, game_id: int) -> None:
    """Schedule a confirmation timeout for this player/game pair."""
    from app.database import SessionLocal

    async def _timeout_job():
        await asyncio.sleep(settings.CONFIRM_TIMEOUT_SECONDS)
        db = SessionLocal()
        try:
            handle_timeout(player_id, game_id, db)
            db.commit()
            broadcast_update("game_update")
        except Exception as e:
            logger.error(f"Timeout job error for player {player_id} game {game_id}: {e}")
            db.rollback()
        finally:
            db.close()
        _timeout_tasks.pop((player_id, game_id), None)

    key = (player_id, game_id)
    if key in _timeout_tasks and not _timeout_tasks[key].done():
        return  # already scheduled

    if _main_loop is None or _main_loop.is_closed():
        logger.warning("No event loop available — timeout not scheduled.")
        return

    future = asyncio.run_coroutine_threadsafe(_timeout_job(), _main_loop)
    _timeout_tasks[key] = future


# ---------------------------------------------------------------------------
# Notification + slot creation
# ---------------------------------------------------------------------------

def _notify_slot(slot: GameSlot, game: Game, db: Session) -> None:
    slot.notified_at = datetime.utcnow()
    db.flush()
    notify_player(slot.player, game)
    _schedule_timeout(slot.player_id, game.id)


def _create_slot_and_notify(db: Session, game: Game, player_id: int) -> GameSlot:
    slot = GameSlot(
        game_id=game.id,
        player_id=player_id,
        position=_next_slot_position(game),
        status=SlotStatus.PENDING_CONFIRMATION,
    )
    db.add(slot)
    db.flush()
    db.refresh(slot)  # load player relationship
    _notify_slot(slot, game, db)
    return slot


# ---------------------------------------------------------------------------
# Fill an open slot from the waiting list
# ---------------------------------------------------------------------------

def fill_slot(db: Session, game: Game) -> bool:
    """Pull the next eligible player from the queue and assign them to the game.
    Skips players who already have an active slot in this game (e.g. deferred players
    who were prepended to the front but shouldn't be re-drawn for the same game).
    Returns True if a player was found, False if no eligible player exists.
    """
    # A player who already has ANY slot in this game (regardless of status) should
    # not be drawn again — prevents double-slotting after decline/defer/timeout.
    already_slotted = {s.player_id for s in game.slots}

    queue = get_queue(db)
    next_entry = next(
        (e for e in queue if e.player_id not in already_slotted),
        None
    )

    if next_entry is None:
        # No eligible players — start with whoever confirmed so far
        confirmed = _confirmed_count(game)
        if confirmed > 0 and game.status == GameStatus.OPEN:
            game.status = GameStatus.IN_PROGRESS
            game.started_at = datetime.utcnow()
            db.flush()
        return False

    player_id = next_entry.player_id
    _remove_from_queue(db, player_id)
    _create_slot_and_notify(db, game, player_id)
    db.expire(game)  # force slots to reload on next access
    return True


# ---------------------------------------------------------------------------
# Main scheduling functions
# ---------------------------------------------------------------------------

def assign_next_game(db: Session) -> Optional[Game]:
    """Create and populate the next game from the waiting list."""
    queue = get_queue(db)
    if not queue:
        logger.info("No players in queue — no game to schedule.")
        return None

    game = Game(
        status=GameStatus.OPEN,
        max_players=settings.MAX_PLAYERS,
    )
    db.add(game)
    db.flush()

    if len(queue) <= settings.MAX_PLAYERS:
        # Everyone plays immediately — no confirmation needed
        for i, entry in enumerate(queue, start=1):
            slot = GameSlot(
                game_id=game.id,
                player_id=entry.player_id,
                position=i,
                status=SlotStatus.CONFIRMED,
                notified_at=datetime.utcnow(),
                responded_at=datetime.utcnow(),
            )
            db.add(slot)
        db.query(WaitingList).delete()
        game.status = GameStatus.IN_PROGRESS
        game.started_at = datetime.utcnow()
        db.flush()
        logger.info(f"Game {game.id} started immediately with {len(queue)} players.")
    else:
        # Notify first MAX_PLAYERS one-by-one (chain: each response triggers the next)
        candidates = queue[: settings.MAX_PLAYERS]
        for entry in candidates:
            _remove_from_queue(db, entry.player_id)
            _create_slot_and_notify(db, game, entry.player_id)

    # Expire and reload so the returned game object has a current .slots collection
    db.expire(game)
    return game


def handle_confirmation(player_id: int, game_id: int, response: str, db: Session) -> None:
    """Process a yes / no / defer response."""
    response = response.strip().lower()
    if response not in ("yes", "no", "defer"):
        raise ValueError(f"Invalid response '{response}'. Must be yes, no, or defer.")

    slot = (
        db.query(GameSlot)
        .filter(GameSlot.game_id == game_id, GameSlot.player_id == player_id)
        .first()
    )
    if not slot:
        raise LookupError(f"No slot for player {player_id} in game {game_id}.")

    if slot.status != SlotStatus.PENDING_CONFIRMATION:
        logger.warning(f"Player {player_id} responded to game {game_id} but slot is {slot.status}.")
        return

    _cancel_timeout(player_id, game_id)
    slot.responded_at = datetime.utcnow()

    game = db.query(Game).filter(Game.id == game_id).first()

    if response == "yes":
        slot.status = SlotStatus.CONFIRMED
        db.flush()
        # Check if we have enough confirmed players to start
        if _confirmed_count(game) + _pending_count(game) == 0:
            # All slots resolved
            if _confirmed_count(game) > 0:
                game.status = GameStatus.IN_PROGRESS
                game.started_at = datetime.utcnow()
        elif _pending_count(game) == 0:
            # All pending resolved
            if _confirmed_count(game) > 0:
                game.status = GameStatus.IN_PROGRESS
                game.started_at = datetime.utcnow()
        logger.info(f"Player {player_id} confirmed for game {game_id}.")

    elif response == "no":
        slot.status = SlotStatus.DECLINED
        db.flush()
        _append_to_queue(db, player_id)
        fill_slot(db, game)
        logger.info(f"Player {player_id} declined game {game_id} — moved to end of queue.")

    elif response == "defer":
        slot.status = SlotStatus.DECLINED
        db.flush()
        # Fill the slot from the current queue FIRST (so the deferred player
        # doesn't immediately get re-notified), then prepend them so they are
        # first in line for the next available slot / next game.
        fill_slot(db, game)
        _prepend_to_queue(db, player_id)
        logger.info(f"Player {player_id} deferred game {game_id} — moved to front of queue.")


def handle_timeout(player_id: int, game_id: int, db: Session) -> None:
    """Called when a player doesn't respond within the configured timeout."""
    slot = (
        db.query(GameSlot)
        .filter(GameSlot.game_id == game_id, GameSlot.player_id == player_id)
        .first()
    )
    if not slot or slot.status != SlotStatus.PENDING_CONFIRMATION:
        return

    slot.status = SlotStatus.TIMED_OUT
    slot.responded_at = datetime.utcnow()
    db.flush()

    game = db.query(Game).filter(Game.id == game_id).first()
    _append_to_queue(db, player_id)
    fill_slot(db, game)
    logger.info(f"Player {player_id} timed out for game {game_id} — moved to end of queue.")


def end_game(game_id: int, db: Session) -> Game:
    """Mark a game as finished and rotate court players to end of waiting list."""
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise LookupError(f"Game {game_id} not found.")

    game.status = GameStatus.FINISHED
    game.ended_at = datetime.utcnow()
    db.flush()

    # Cancel any outstanding confirmation timeouts for this game
    for slot in game.slots:
        _cancel_timeout(slot.player_id, game_id)

    # Rotate confirmed court players to end of queue (in seat order)
    confirmed = sorted(
        [s for s in game.slots if s.status == SlotStatus.CONFIRMED],
        key=lambda s: s.position,
    )
    for slot in confirmed:
        _append_to_queue(db, slot.player_id)

    db.flush()
    assign_next_game(db)
    return game


def join_queue(player_id: int, db: Session) -> WaitingList:
    entry = _append_to_queue(db, player_id)
    broadcast_update("queue_update")
    return entry


def leave_queue(player_id: int, db: Session) -> None:
    _remove_from_queue(db, player_id)
    broadcast_update("queue_update")
