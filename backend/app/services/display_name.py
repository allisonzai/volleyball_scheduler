from __future__ import annotations
from typing import Optional
from sqlalchemy.orm import Session
from app.models.player import Player


def resolve_display_name(first_name: str, last_name: str, phone: str, db: Session, exclude_id: Optional[int] = None) -> str:
    """Generate a unique display name: 'FirstName L.' or 'FirstName L. XX' if duplicate."""
    # Prefix shared by all variants of this name, e.g. "Alice J"
    prefix = f"{first_name} {last_name[0]}"
    base = f"{prefix}."

    # Find all players sharing this name prefix (bare name OR any suffix variant)
    query = db.query(Player).filter(
        Player.display_name.like(f"{prefix}%")
    )
    if exclude_id is not None:
        query = query.filter(Player.id != exclude_id)

    conflicts = query.all()

    if not conflicts:
        return base  # No one else has this name — use the plain form

    # Build a candidate for the new player using the last 2 digits of their phone
    suffix = phone[-2:]
    candidate = f"{prefix} {suffix}."

    # Update any existing player that still has the bare name (no suffix yet)
    for conflict in conflicts:
        if conflict.display_name == base:
            conflict_suffix = conflict.phone[-2:]
            if conflict_suffix != suffix:
                conflict.display_name = f"{prefix} {conflict_suffix}."
            else:
                # Extremely rare: same last-2 digits — use last 4
                conflict.display_name = f"{prefix} {conflict.phone[-4:]}."
                candidate = f"{prefix} {phone[-4:]}."
            db.flush()

    return candidate
