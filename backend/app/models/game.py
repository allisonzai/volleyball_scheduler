from __future__ import annotations
from datetime import datetime
from typing import Optional, List
from enum import Enum
from sqlalchemy import String, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class GameStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    FINISHED = "finished"


class Game(Base):
    __tablename__ = "games"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default=GameStatus.OPEN)
    max_players: Mapped[int] = mapped_column(Integer, default=12)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    slots: Mapped[List["GameSlot"]] = relationship("GameSlot", back_populates="game")  # noqa: F821
