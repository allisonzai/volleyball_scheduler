from __future__ import annotations
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session

from app.models.event_log import EventLog


def log_event(
    db: Session,
    event_type: str,
    description: str,
    game_id: Optional[int] = None,
    game_number: Optional[int] = None,
) -> None:
    entry = EventLog(
        event_type=event_type,
        description=description,
        game_id=game_id,
        game_number=game_number,
        created_at=datetime.utcnow(),
    )
    db.add(entry)
    db.flush()
