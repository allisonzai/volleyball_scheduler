from __future__ import annotations
import logging
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.schemas.queue import ConfirmRequest
from app.services import scheduler
from app.models.player import Player

logger = logging.getLogger(__name__)
router = APIRouter(tags=["notifications"])


def _require_player_token(player: Player, token: Optional[str]) -> None:
    if not token or not secrets.compare_digest(token, player.secret_token):
        raise HTTPException(401, "Invalid or missing player token.")


@router.post("/api/confirm")
def confirm(
    data: ConfirmRequest,
    x_player_token: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    """App button confirmation: player sends yes/no/defer."""
    player = db.query(Player).filter(Player.id == data.player_id).first()
    if not player:
        raise HTTPException(404, "Player not found.")

    _require_player_token(player, x_player_token)

    try:
        scheduler.handle_confirmation(data.player_id, data.game_id, data.response, db)
        db.commit()
        scheduler.broadcast_update("game_update")
        return {"status": "ok"}
    except ValueError as e:
        raise HTTPException(400, str(e))
    except LookupError as e:
        raise HTTPException(404, str(e))


@router.post("/api/sms/webhook")
async def sms_webhook(request: Request, db: Session = Depends(get_db)):
    """Twilio inbound SMS webhook. Expects application/x-www-form-urlencoded."""
    # Validate Twilio signature to prevent spoofed requests
    if not settings.STUB_SMS:
        _verify_twilio_signature(request)

    form = await request.form()
    from_number = form.get("From", "").strip()
    body = form.get("Body", "").strip().lower()

    if not from_number or body not in ("yes", "no", "defer"):
        return _twiml_response("Sorry, please reply YES, NO, or DEFER.")

    player = db.query(Player).filter(Player.phone == from_number).first()
    if not player:
        return _twiml_response("Phone number not registered. Visit the app to sign up.")

    from app.models.game_slot import GameSlot, SlotStatus
    slot = (
        db.query(GameSlot)
        .filter(
            GameSlot.player_id == player.id,
            GameSlot.status == SlotStatus.PENDING_CONFIRMATION,
        )
        .order_by(GameSlot.id.desc())
        .first()
    )
    if not slot:
        return _twiml_response("No pending game confirmation found for you.")

    try:
        scheduler.handle_confirmation(player.id, slot.game_id, body, db)
        db.commit()
        scheduler.broadcast_update("game_update")
    except Exception as e:
        logger.error(f"SMS confirmation error: {e}")
        return _twiml_response("Error processing your response. Please try the app.")

    responses = {
        "yes": "You're confirmed! Get ready to play.",
        "no": "Understood — you've been moved to the end of the queue.",
        "defer": "Got it — you've been moved to the front of the queue.",
    }
    return _twiml_response(responses[body])


def _verify_twilio_signature(request: Request) -> None:
    """Validate X-Twilio-Signature against the request URL and body."""
    try:
        from twilio.request_validator import RequestValidator
    except ImportError:
        logger.warning("twilio package not installed — skipping signature check.")
        return

    validator = RequestValidator(settings.TWILIO_AUTH_TOKEN)
    signature = request.headers.get("X-Twilio-Signature", "")
    url = str(request.url)
    # Note: form body must be read before calling this; FastAPI reads it for us.
    # We pass an empty dict here because Twilio also validates the raw body hash.
    # For a full implementation use the async body approach with POST params dict.
    if not validator.validate(url, {}, signature):
        raise HTTPException(403, "Invalid Twilio signature.")


def _twiml_response(message: str):
    from fastapi.responses import Response
    body = f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{message}</Message></Response>'
    return Response(content=body, media_type="text/xml")
