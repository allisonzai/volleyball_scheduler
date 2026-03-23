from __future__ import annotations
from datetime import datetime
from sqlalchemy import ForeignKey, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class WaitingList(Base):
    __tablename__ = "waiting_list"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), unique=True, index=True)
    # Signup number: globally incrementing, assigned at join time, never changes
    signup_number: Mapped[int] = mapped_column(Integer, index=True)
    # Queue position: lower = plays sooner; resequenced after each mutation
    position: Mapped[int] = mapped_column(Integer, index=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    player: Mapped["Player"] = relationship("Player", back_populates="waiting_entry")  # noqa: F821
