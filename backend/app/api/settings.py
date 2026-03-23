from __future__ import annotations
import secrets as _secrets
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.config import settings

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _require_operator(token: Optional[str]) -> None:
    if not token or not _secrets.compare_digest(token, settings.OPERATOR_SECRET):
        raise HTTPException(401, "Invalid or missing operator secret.")


class SettingsOut(BaseModel):
    confirm_timeout_seconds: int
    max_players: int


class SettingsPatch(BaseModel):
    confirm_timeout_seconds: Optional[int] = None


@router.get("", response_model=SettingsOut)
def get_settings():
    return SettingsOut(
        confirm_timeout_seconds=settings.CONFIRM_TIMEOUT_SECONDS,
        max_players=settings.MAX_PLAYERS,
    )


@router.patch("", response_model=SettingsOut)
def update_settings(
    body: SettingsPatch,
    x_operator_secret: Optional[str] = Header(default=None),
):
    _require_operator(x_operator_secret)

    if body.confirm_timeout_seconds is not None:
        if body.confirm_timeout_seconds < 30:
            raise HTTPException(400, "confirm_timeout_seconds must be at least 30.")
        settings.CONFIRM_TIMEOUT_SECONDS = body.confirm_timeout_seconds

    return SettingsOut(
        confirm_timeout_seconds=settings.CONFIRM_TIMEOUT_SECONDS,
        max_players=settings.MAX_PLAYERS,
    )
