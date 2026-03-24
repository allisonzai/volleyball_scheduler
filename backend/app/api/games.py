from __future__ import annotations
import secrets
from typing import Optional, List

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.game import Game, GameStatus
from app.models.game_slot import SlotStatus
from app.schemas.game import GameOut, SlotOut, GameCreate
from app.services import scheduler

router = APIRouter(prefix="/api/games", tags=["games"])


def _require_operator(token: Optional[str]) -> None:
    if not token or not secrets.compare_digest(token, settings.OPERATOR_SECRET):
        raise HTTPException(401, "Invalid or missing operator secret.")


def _slot_to_schema(slot) -> SlotOut:
    return SlotOut(
        id=slot.id,
        player_id=slot.player_id,
        position=slot.position,
        status=slot.status,
        display_name=slot.player.display_name,
        signup_number=slot.signup_number,
        notified_at=slot.notified_at,
    )


def _game_to_schema(game: Game, db: Session) -> GameOut:
    slots = [_slot_to_schema(slot) for slot in sorted(game.slots, key=lambda s: s.position)]
    return GameOut(
        id=game.id,
        game_number=game.game_number,
        status=game.status,
        max_players=game.max_players,
        started_at=game.started_at,
        ended_at=game.ended_at,
        created_at=game.created_at,
        slots=slots,
    )


@router.get("/current", response_model=Optional[GameOut])
def get_current_game(db: Session = Depends(get_db)):
    game = (
        db.query(Game)
        .filter(Game.status.in_([GameStatus.OPEN, GameStatus.IN_PROGRESS]))
        .order_by(Game.id.desc())
        .first()
    )
    if not game:
        return None
    return _game_to_schema(game, db)


@router.get("", response_model=list[GameOut])
def list_games(status: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(Game)
    if status:
        q = q.filter(Game.status == status)
    games = q.order_by(Game.id.desc()).all()
    return [_game_to_schema(g, db) for g in games]


@router.get("/{game_id}", response_model=GameOut)
def get_game(game_id: int, db: Session = Depends(get_db)):
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(404, "Game not found.")
    return _game_to_schema(game, db)


@router.post("/reset", status_code=204)
def reset_all(
    x_operator_secret: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    _require_operator(x_operator_secret)
    scheduler.reset_all(db)
    db.commit()


@router.delete("/history", status_code=204)
def clear_history(
    x_operator_secret: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    _require_operator(x_operator_secret)
    scheduler.clear_history(db)
    db.commit()


@router.post("/start", response_model=GameOut, status_code=201)
def start_game(
    x_operator_secret: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    _require_operator(x_operator_secret)
    active = (
        db.query(Game)
        .filter(Game.status.in_([GameStatus.OPEN, GameStatus.IN_PROGRESS]))
        .first()
    )
    if active:
        raise HTTPException(400, "A game is already in progress.")

    game = scheduler.assign_next_game(db)
    if not game:
        raise HTTPException(400, "No players in the queue.")

    db.commit()
    db.refresh(game)
    scheduler.broadcast_update("game_update")
    return _game_to_schema(game, db)


@router.post("/{game_id}/begin", response_model=GameOut)
def begin_game(
    game_id: int,
    x_operator_secret: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    """Force the staging phase to end and start the game immediately with
    whoever has already confirmed.  Pending slots are cancelled."""
    _require_operator(x_operator_secret)
    try:
        game = scheduler.force_start_game(game_id, db)
    except (LookupError, ValueError) as e:
        raise HTTPException(400, str(e))
    db.commit()
    db.refresh(game)
    scheduler.broadcast_update("game_update")
    return _game_to_schema(game, db)


@router.post("/{game_id}/leave", status_code=204)
def leave_game(
    game_id: int,
    x_player_token: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    from app.models.game_slot import GameSlot
    if not x_player_token:
        raise HTTPException(401, "Missing player token.")
    # Find the player by token
    from app.models.player import Player
    import secrets as _secrets
    players = db.query(Player).all()
    player = next((p for p in players if _secrets.compare_digest(p.secret_token, x_player_token)), None)
    if not player:
        raise HTTPException(401, "Invalid player token.")
    try:
        scheduler.leave_game(player.id, game_id, db)
    except LookupError as e:
        raise HTTPException(400, str(e))
    db.commit()


@router.post("/{game_id}/end", response_model=GameOut)
def end_game(
    game_id: int,
    x_operator_secret: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    _require_operator(x_operator_secret)
    try:
        game = scheduler.end_game(game_id, db)
    except LookupError as e:
        raise HTTPException(404, str(e))

    db.commit()
    db.refresh(game)
    scheduler.broadcast_update("game_update")
    return _game_to_schema(game, db)
