from __future__ import annotations
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Player(Base):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(150))
    expo_push_token: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Authentication
    secret_token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))

    # Verification
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verification_code: Mapped[Optional[str]] = mapped_column(String(6), nullable=True)
    verification_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    slots: Mapped[List["GameSlot"]] = relationship("GameSlot", back_populates="player")  # noqa: F821
    waiting_entry: Mapped[Optional["WaitingList"]] = relationship("WaitingList", back_populates="player", uselist=False)  # noqa: F821
