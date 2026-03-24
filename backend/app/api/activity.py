from __future__ import annotations
from typing import List, Optional
from datetime import datetime

import secrets as _secrets
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional as _Optional

from app.config import settings
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


@router.delete("", status_code=204)
def clear_activity(
    x_operator_secret: _Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    if not x_operator_secret or not _secrets.compare_digest(
        x_operator_secret, settings.OPERATOR_SECRET
    ):
        raise HTTPException(401, "Invalid or missing operator secret.")
    db.query(EventLog).delete()
    db.commit()
