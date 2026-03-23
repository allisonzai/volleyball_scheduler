from __future__ import annotations
from datetime import datetime
from typing import Optional
from enum import Enum
from sqlalchemy import ForeignKey, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class SlotStatus(str, Enum):
    PENDING_CONFIRMATION = "pending_confirmation"
    CONFIRMED = "confirmed"
    DECLINED = "declined"
    TIMED_OUT = "timed_out"
    WITHDRAWN = "withdrawn"


class GameSlot(Base):
    __tablename__ = "game_slots"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), index=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), default=SlotStatus.PENDING_CONFIRMATION)
    notified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    responded_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    game: Mapped["Game"] = relationship("Game", back_populates="slots")  # noqa: F821
    player: Mapped["Player"] = relationship("Player", back_populates="slots")  # noqa: F821
