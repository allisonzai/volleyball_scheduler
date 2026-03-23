from __future__ import annotations
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models.game import GameStatus
from app.models.game_slot import GameSlot, SlotStatus
from app.models.player import Player
from app.models.waiting_list import WaitingList
from app.schemas.queue import QueueEntry, QueueJoin
from app.services import scheduler

router = APIRouter(prefix="/api/queue", tags=["queue"])


def _require_player_token(player: Player, token: Optional[str]) -> None:
    """Raise 401 if the X-Player-Token header does not match the player's secret."""
    import secrets as _secrets
    if not token or not _secrets.compare_digest(token, player.secret_token):
        raise HTTPException(401, "Invalid or missing player token.")


def _entry_to_schema(entry: WaitingList) -> QueueEntry:
    return QueueEntry(
        player_id=entry.player_id,
        display_name=entry.player.display_name,
        signup_number=entry.signup_number,
        position=entry.position,
        joined_at=entry.joined_at,
    )


@router.get("", response_model=list[QueueEntry])
def get_queue(db: Session = Depends(get_db)):
    entries = scheduler.get_queue(db)
    return [_entry_to_schema(e) for e in entries]


@router.post("/join", response_model=QueueEntry, status_code=201)
def join_queue(
    data: QueueJoin,
    x_player_token: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    player = db.query(Player).filter(Player.id == data.player_id).first()
    if not player:
        raise HTTPException(404, "Player not found.")

    _require_player_token(player, x_player_token)

    if not player.is_verified:
        raise HTTPException(403, "Player account is not verified.")

    existing = db.query(WaitingList).filter(WaitingList.player_id == data.player_id).first()
    if existing:
        raise HTTPException(400, "Player is already in the queue.")

    # Block players who are actively playing in an open/in-progress game
    from app.models.game import Game
    active_slot = (
        db.query(GameSlot)
        .join(Game, GameSlot.game_id == Game.id)
        .filter(
            GameSlot.player_id == data.player_id,
            GameSlot.status.in_([SlotStatus.PENDING_CONFIRMATION, SlotStatus.CONFIRMED]),
            Game.status.in_([GameStatus.OPEN, GameStatus.IN_PROGRESS]),
        )
        .first()
    )
    if active_slot:
        raise HTTPException(400, "Player is currently in an active game and cannot join the queue.")

    entry = scheduler.join_queue(data.player_id, db)
    db.commit()
    db.refresh(entry)
    scheduler.broadcast_update("queue_update")
    return _entry_to_schema(entry)


@router.delete("/{player_id}", status_code=204)
def leave_queue(
    player_id: int,
    x_player_token: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    player = db.query(Player).filter(Player.id == player_id).first()
    if not player:
        raise HTTPException(404, "Player not found.")

    _require_player_token(player, x_player_token)

    existing = db.query(WaitingList).filter(WaitingList.player_id == player_id).first()
    if not existing:
        raise HTTPException(404, "Player is not in the queue.")
    scheduler.leave_queue(player_id, db)
    db.commit()


@router.post("/{player_id}/defer", response_model=QueueEntry)
def defer_in_queue(
    player_id: int,
    x_player_token: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    player = db.query(Player).filter(Player.id == player_id).first()
    if not player:
        raise HTTPException(404, "Player not found.")

    _require_player_token(player, x_player_token)

    try:
        entry = scheduler.defer_in_queue(player_id, db)
    except LookupError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))

    db.commit()
    db.refresh(entry)
    return _entry_to_schema(entry)
