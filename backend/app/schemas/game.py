from __future__ import annotations
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel
from app.models.game import GameStatus
from app.models.game_slot import SlotStatus


class SlotOut(BaseModel):
    id: int
    player_id: int
    position: int
    status: SlotStatus
    display_name: str
    signup_number: Optional[int] = None
    notified_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class GameOut(BaseModel):
    id: int
    game_number: Optional[int] = None
    status: GameStatus
    max_players: int
    started_at: datetime | None
    ended_at: datetime | None
    created_at: datetime
    slots: list[SlotOut] = []

    model_config = {"from_attributes": True}


class GameCreate(BaseModel):
    max_players: int = 12
