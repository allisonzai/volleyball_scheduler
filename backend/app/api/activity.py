from __future__ import annotations
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.event_log import EventLog

router = APIRouter(prefix="/api/activity", tags=["activity"])


class EventLogOut(BaseModel):
    id: int
    event_type: str
    description: str
    game_id: Optional[int] = None
    game_number: Optional[int] = None
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("", response_model=List[EventLogOut])
def get_activity(
    limit: int = Query(default=200, le=1000),
    db: Session = Depends(get_db),
):
    events = (
        db.query(EventLog)
        .order_by(EventLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return events
