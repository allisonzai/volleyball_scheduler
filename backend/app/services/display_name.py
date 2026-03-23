from __future__ import annotations
from typing import Optional
from sqlalchemy.orm import Session
from app.models.player import Player


def resolve_display_name(first_name: str, last_name: str, phone: str, db: Session, exclude_id: Optional[int] = None) -> str:
    """Generate a unique display name: 'FirstName L' or 'FirstName L - 4242' if duplicate."""
    prefix = f"{first_name} {last_name[0]}"
    base = prefix  # no trailing period

    query = db.query(Player).filter(
        Player.display_name.like(f"{prefix}%")
    )
    if exclude_id is not None:
        query = query.filter(Player.id != exclude_id)

    conflicts = query.all()

    if not conflicts:
        return base

    # Use last 4 digits of phone for disambiguation
    suffix = phone[-4:]
    candidate = f"{prefix} [{suffix}]"

    # Update any existing player that still has the bare name
    for conflict in conflicts:
        if conflict.display_name == base:
            conflict.display_name = f"{prefix} [{conflict.phone[-4:]}]"
            db.flush()

    return candidate
