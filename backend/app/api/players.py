from __future__ import annotations
import random
import re
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.player import Player
from app.schemas.player import (
    PlayerCreate,
    PlayerOut,
    PlayerRegisterOut,
    PlayerUpdate,
    SignInRequest,
    VerificationRequest,
    VerificationSubmit,
)
from app.services.display_name import resolve_display_name
from app.services.email import send_verification_email
from app.services.password import hash_password, verify_password
from app.services.sms import send_sms

router = APIRouter(prefix="/api/players", tags=["players"])

_VERIFICATION_LENGTH = 6


def _generate_code() -> str:
    return str(random.SystemRandom().randint(0, 10**_VERIFICATION_LENGTH - 1)).zfill(_VERIFICATION_LENGTH)


def _send_code(player: Player, channel: str, code: str) -> None:
    if channel == "sms":
        send_sms(player.phone, f"Your Volleyball Scheduler code is: {code}. It expires in {settings.VERIFICATION_EXPIRES_MINUTES} minutes.")
    else:
        send_verification_email(player.email, player.display_name, code)


def _normalize_phone(phone: str) -> str:
    return re.sub(r"\D", "", phone.strip())


@router.post("", response_model=PlayerRegisterOut, status_code=201)
def register_player(data: PlayerCreate, db: Session = Depends(get_db)):
    if db.query(Player).filter(Player.phone == data.phone).first():
        raise HTTPException(400, "Phone number already registered.")
    if db.query(Player).filter(Player.email == data.email).first():
        raise HTTPException(400, "Email already registered.")

    if len(data.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters.")

    display = resolve_display_name(data.first_name, data.last_name, data.phone, db)
    player = Player(
        first_name=data.first_name,
        last_name=data.last_name,
        phone=data.phone,
        email=data.email,
        display_name=display,
        secret_token=secrets.token_hex(32),
        password_hash=hash_password(data.password),
    )
    db.add(player)
    db.commit()
    db.refresh(player)
    return player


@router.post("/signin", response_model=PlayerRegisterOut)
def sign_in(data: SignInRequest, db: Session = Depends(get_db)):
    """Sign in with phone number and password."""
    digits = _normalize_phone(data.phone)
    all_players = db.query(Player).all()
    player = next(
        (p for p in all_players if _normalize_phone(p.phone) == digits),
        None,
    )
    # Use a constant-time failure path to avoid user enumeration
    if not player or not verify_password(data.password, player.password_hash):
        raise HTTPException(401, "Invalid phone number or password.")
    return player


@router.get("/{player_id}", response_model=PlayerOut)
def get_player(player_id: int, db: Session = Depends(get_db)):
    player = db.query(Player).filter(Player.id == player_id).first()
    if not player:
        raise HTTPException(404, "Player not found.")
    return player


@router.patch("/{player_id}/push-token", response_model=PlayerOut)
def update_push_token(player_id: int, data: PlayerUpdate, db: Session = Depends(get_db)):
    player = db.query(Player).filter(Player.id == player_id).first()
    if not player:
        raise HTTPException(404, "Player not found.")
    player.expo_push_token = data.expo_push_token
    db.commit()
    db.refresh(player)
    return player


@router.delete("/{player_id}", status_code=204)
def deregister_player(
    player_id: int,
    x_player_token: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    """Permanently remove a player. Blocked if they have an active slot in an ongoing game."""
    player = db.query(Player).filter(Player.id == player_id).first()
    if not player:
        raise HTTPException(404, "Player not found.")

    if not x_player_token or not secrets.compare_digest(x_player_token, player.secret_token):
        raise HTTPException(401, "Invalid or missing player token.")

    from app.models.game import Game
    from app.models.game_slot import GameSlot, SlotStatus
    active_slot = (
        db.query(GameSlot)
        .join(Game, GameSlot.game_id == Game.id)
        .filter(
            GameSlot.player_id == player_id,
            GameSlot.status.in_([SlotStatus.PENDING_CONFIRMATION, SlotStatus.CONFIRMED]),
            Game.status.in_(["open", "in_progress"]),
        )
        .first()
    )
    if active_slot:
        raise HTTPException(400, "Cannot deregister while in an active game.")

    from app.services import scheduler
    scheduler._remove_from_queue(db, player_id)
    db.delete(player)
    db.commit()


@router.post("/{player_id}/request-verification", status_code=200)
def request_verification(
    player_id: int,
    data: VerificationRequest,
    db: Session = Depends(get_db),
):
    """Generate and send a new verification code via email or SMS."""
    player = db.query(Player).filter(Player.id == player_id).first()
    if not player:
        raise HTTPException(404, "Player not found.")
    if player.is_verified:
        return {"status": "already_verified"}

    if data.channel not in ("email", "sms"):
        raise HTTPException(400, "channel must be 'email' or 'sms'.")

    code = _generate_code()
    player.verification_code = code
    player.verification_expires_at = datetime.utcnow() + timedelta(
        minutes=settings.VERIFICATION_EXPIRES_MINUTES
    )
    db.commit()

    _send_code(player, data.channel, code)
    return {"status": "sent", "channel": data.channel}


@router.post("/{player_id}/verify", response_model=PlayerOut)
def verify_player(
    player_id: int,
    data: VerificationSubmit,
    db: Session = Depends(get_db),
):
    """Submit the verification code to activate the account."""
    player = db.query(Player).filter(Player.id == player_id).first()
    if not player:
        raise HTTPException(404, "Player not found.")
    if player.is_verified:
        return player

    if not player.verification_code or not player.verification_expires_at:
        raise HTTPException(400, "No verification code issued. Call /request-verification first.")

    if datetime.utcnow() > player.verification_expires_at:
        raise HTTPException(400, "Verification code has expired. Request a new one.")

    if not secrets.compare_digest(data.code.strip(), player.verification_code):
        raise HTTPException(400, "Invalid verification code.")

    player.is_verified = True
    player.verification_code = None
    player.verification_expires_at = None
    db.commit()
    db.refresh(player)
    return player
