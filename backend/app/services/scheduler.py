from __future__ import annotations
"""
Core scheduling service for volleyball games.

State machine:
  waiting list -> PENDING_CONFIRMATION -> CONFIRMED (playing) or DECLINED/TIMED_OUT -> end of waiting list
"""
import asyncio
import logging
import threading
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.config import settings
from app.models.game import Game, GameStatus
from app.models.game_slot import GameSlot, SlotStatus
from app.models.waiting_list import WaitingList
from app.services.notifications import notify_player

logger = logging.getLogger(__name__)

# In-memory map of (player_id, game_id) -> threading.Timer for confirmation timeouts
_timeout_tasks: dict = {}

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


def _insert_before_first_eligible(db: Session, game: Game, player_id: int, signup_number: Optional[int] = None) -> WaitingList:
    """Re-insert a deferred player at the position vacated by the eligible player
    that fill_slot just promoted into the game.  Concretely: insert immediately
    before the first queue entry whose player has no slot in this game (i.e. has
    not yet deferred for this game).  Players who already have a slot stay ahead
    of the re-inserted player.  Preserves the original signup_number."""
    already_slotted = {s.player_id for s in game.slots}
    queue = get_queue(db)

    first_eligible = next((e for e in queue if e.player_id not in already_slotted), None)

    if first_eligible is None:
        # Everyone remaining in the queue already has a slot — append to end
        max_pos = db.query(func.max(WaitingList.position)).scalar() or 0
        entry = WaitingList(
            player_id=player_id,
            signup_number=signup_number or _next_signup_number(db),
            position=max_pos + 1,
        )
        db.add(entry)
        db.flush()
        _resequence(db)
        return entry

    # Shift entries at first_eligible.position and beyond to make room
    target_pos = first_eligible.position
    db.query(WaitingList).filter(WaitingList.position >= target_pos).update(
        {WaitingList.position: WaitingList.position + 1}
    )
    entry = WaitingList(
        player_id=player_id,
        signup_number=signup_number or _next_signup_number(db),
        position=target_pos,
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
    timer = _timeout_tasks.pop(key, None)
    if timer is not None:
        timer.cancel()


def _schedule_timeout(player_id: int, game_id: int, delay_seconds: Optional[float] = None) -> None:
    """Schedule a confirmation timeout for this player/game pair.
    Uses settings.CONFIRM_TIMEOUT_SECONDS if delay_seconds is not provided."""
    from app.database import SessionLocal

    if delay_seconds is None:
        delay_seconds = settings.CONFIRM_TIMEOUT_SECONDS

    def _timeout_job():
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
    existing = _timeout_tasks.get(key)
    if existing is not None:
        existing.cancel()

    timer = threading.Timer(delay_seconds, _timeout_job)
    timer.daemon = True
    timer.start()
    _timeout_tasks[key] = timer


def reschedule_pending_timeouts(db: Session, new_timeout_seconds: int) -> None:
    """Called when the operator changes the confirmation timeout.
    Cancels every in-flight pending timer and reschedules it so the remaining
    time reflects the new setting.  Players who have already exceeded the new
    timeout are fired immediately (remaining = 0)."""
    active_games = (
        db.query(Game)
        .filter(Game.status.in_([GameStatus.OPEN, GameStatus.IN_PROGRESS]))
        .all()
    )
    now = datetime.utcnow()
    for game in active_games:
        for slot in game.slots:
            if slot.status != SlotStatus.PENDING_CONFIRMATION:
                continue
            if slot.notified_at is None:
                continue
            elapsed = (now - slot.notified_at).total_seconds()
            remaining = max(0.0, new_timeout_seconds - elapsed)
            _schedule_timeout(slot.player_id, game.id, delay_seconds=remaining)
            logger.info(
                f"Rescheduled timeout for player {slot.player_id} game {game.id}: "
                f"{remaining:.1f}s remaining"
            )


# ---------------------------------------------------------------------------
# Notification + slot creation
# ---------------------------------------------------------------------------

def _notify_slot(slot: GameSlot, game: Game, db: Session) -> None:
    slot.notified_at = datetime.utcnow()
    db.flush()
    notify_player(slot.player, game)
    _schedule_timeout(slot.player_id, game.id)


def _create_slot_and_notify(db: Session, game: Game, player_id: int, signup_number: Optional[int] = None) -> GameSlot:
    slot = GameSlot(
        game_id=game.id,
        player_id=player_id,
        position=_next_slot_position(game),
        signup_number=signup_number,
        status=SlotStatus.PENDING_CONFIRMATION,
    )
    db.add(slot)
    db.flush()
    db.refresh(slot)  # load player relationship
    _notify_slot(slot, game, db)
    return slot


# ---------------------------------------------------------------------------
# Fill open slots from the waiting list
# ---------------------------------------------------------------------------

def _try_fill_open_slots(db: Session, game: Game) -> None:
    """Called after any slot resolves. Once no slots remain pending, batch-fill
    missing spots from the queue — or start the game if the queue is exhausted.
    Fills even when confirmed == 0: the batch players are the ones who will
    confirm, so we must give them a chance before deciding the game can't start."""
    db.expire(game)
    if _pending_count(game) > 0:
        return  # still waiting for outstanding responses

    confirmed = _confirmed_count(game)
    needed = game.max_players - confirmed

    if needed <= 0:
        # Full house of confirmed players — start the game
        if game.status == GameStatus.OPEN:
            game.status = GameStatus.IN_PROGRESS
            game.started_at = datetime.utcnow()
            db.flush()
        return

    # Batch-fill: pull up to `needed` replacements from the queue at once.
    # Use allow_requeue=True so deferred players who were re-inserted into the
    # queue are eligible — their DECLINED slot no longer blocks them.
    for _ in range(needed):
        if not fill_slot(db, game, allow_requeue=True):
            break  # queue exhausted
        db.expire(game)


def fill_slot(db: Session, game: Game, allow_requeue: bool = False) -> bool:
    """Pull the next eligible player from the queue and assign them to the game.
    Returns True if a player was found, False if no eligible player exists.

    allow_requeue=False (default): excludes every player who has any slot in
      this game regardless of status.  Used during the live confirmation phase
      so a player who just deferred is not immediately re-drawn.
    allow_requeue=True: excludes only players with an active slot
      (PENDING_CONFIRMATION or CONFIRMED).  Used during batch-fill after all
      pending slots have resolved, so deferred players re-inserted into the
      queue are eligible to fill remaining spots.
    """
    if allow_requeue:
        active_statuses = {SlotStatus.PENDING_CONFIRMATION, SlotStatus.CONFIRMED}
        already_slotted = {s.player_id for s in game.slots if s.status in active_statuses}
    else:
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
    signup_number = next_entry.signup_number
    _remove_from_queue(db, player_id)
    _create_slot_and_notify(db, game, player_id, signup_number)
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

    # Always notify players and require confirmation, regardless of queue size
    candidates = queue[: settings.MAX_PLAYERS]
    for entry in candidates:
        signup_number = entry.signup_number
        _remove_from_queue(db, entry.player_id)
        _create_slot_and_notify(db, game, entry.player_id, signup_number)

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
        _try_fill_open_slots(db, game)
        logger.info(f"Player {player_id} confirmed for game {game_id}.")

    elif response == "no":
        slot.status = SlotStatus.DECLINED
        db.flush()
        _remove_from_queue(db, player_id)
        # Don't fill immediately — wait until all pending slots resolve, then batch-fill
        _try_fill_open_slots(db, game)
        logger.info(f"Player {player_id} declined game {game_id} — removed from queue.")

    elif response == "defer":
        slot.status = SlotStatus.DECLINED
        db.flush()
        # fill_slot promotes the first eligible queue player into the vacated slot
        # (and calls db.expire(game) so game.slots reloads on next access).
        # Then re-insert the deferred player right before the next eligible queue
        # entry, preserving their original signup_number.
        fill_slot(db, game)
        _insert_before_first_eligible(db, game, player_id, slot.signup_number)
        logger.info(f"Player {player_id} deferred game {game_id} — swapped with first eligible queue player.")


def handle_timeout(player_id: int, game_id: int, db: Session) -> None:
    """Called when a player doesn't respond within the configured timeout.
    No response is treated as 'no': player is declined and moved to end of queue."""
    slot = (
        db.query(GameSlot)
        .filter(GameSlot.game_id == game_id, GameSlot.player_id == player_id)
        .first()
    )
    if not slot or slot.status != SlotStatus.PENDING_CONFIRMATION:
        return
    logger.info(f"Player {player_id} timed out for game {game_id} — defaulting to 'no'.")
    handle_confirmation(player_id, game_id, "no", db)


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
    return game


def reset_all(db: Session) -> None:
    """Cancel active games and clear the waiting list. Player accounts and
    game history are kept."""
    # Cancel all pending timeout timers
    for timer in list(_timeout_tasks.values()):
        timer.cancel()
    _timeout_tasks.clear()

    # Mark any open/in-progress games as finished
    active_games = (
        db.query(Game)
        .filter(Game.status.in_([GameStatus.OPEN, GameStatus.IN_PROGRESS]))
        .all()
    )
    for game in active_games:
        game.status = GameStatus.FINISHED
        game.ended_at = datetime.utcnow()

    # Clear the entire waiting list
    db.query(WaitingList).delete()
    db.flush()
    broadcast_update("game_update")


def clear_history(db: Session) -> None:
    """Delete all finished game records and their slots, resetting the game
    ID sequence back to 1 on next start."""
    finished_ids = [
        g.id for g in db.query(Game).filter(Game.status == GameStatus.FINISHED).all()
    ]
    if finished_ids:
        db.query(GameSlot).filter(GameSlot.game_id.in_(finished_ids)).delete(
            synchronize_session=False
        )
        db.query(Game).filter(Game.id.in_(finished_ids)).delete(
            synchronize_session=False
        )
    db.flush()
    broadcast_update("game_update")


def join_queue(player_id: int, db: Session) -> WaitingList:
    entry = _append_to_queue(db, player_id)
    broadcast_update("queue_update")
    return entry


def leave_queue(player_id: int, db: Session) -> None:
    _remove_from_queue(db, player_id)
    broadcast_update("queue_update")


def defer_in_queue(player_id: int, db: Session) -> WaitingList:
    """Swap this waiting-list player with the next person behind them."""
    entry = db.query(WaitingList).filter(WaitingList.player_id == player_id).first()
    if not entry:
        raise LookupError("Player is not in the queue.")

    next_entry = (
        db.query(WaitingList)
        .filter(WaitingList.position > entry.position)
        .order_by(WaitingList.position)
        .first()
    )
    if not next_entry:
        raise ValueError("No next player to swap with — already last in queue.")

    entry.position, next_entry.position = next_entry.position, entry.position
    db.flush()
    broadcast_update("queue_update")
    return entry


def leave_game(player_id: int, game_id: int, db: Session) -> None:
    """Allow a confirmed player to leave an active game mid-play."""
    slot = (
        db.query(GameSlot)
        .filter(GameSlot.game_id == game_id, GameSlot.player_id == player_id)
        .first()
    )
    if not slot or slot.status != SlotStatus.CONFIRMED:
        raise LookupError("No active confirmed slot found for this player in this game.")

    game = db.query(Game).filter(Game.id == game_id).first()
    if not game or game.status not in (GameStatus.OPEN, GameStatus.IN_PROGRESS):
        raise LookupError("Game is not active.")

    slot.status = SlotStatus.WITHDRAWN
    slot.responded_at = datetime.utcnow()
    db.flush()

    _remove_from_queue(db, player_id)
    fill_slot(db, game)
    logger.info(f"Player {player_id} withdrew from game {game_id} mid-play.")
    broadcast_update("game_update")
