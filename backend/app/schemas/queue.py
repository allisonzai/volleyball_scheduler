from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel


class QueueEntry(BaseModel):
    player_id: int
    display_name: str
    signup_number: int
    position: int
    joined_at: datetime

    model_config = {"from_attributes": True}


class QueueJoin(BaseModel):
    player_id: int


class ConfirmRequest(BaseModel):
    player_id: int
    game_id: int
    response: str  # "yes", "no", "defer"
