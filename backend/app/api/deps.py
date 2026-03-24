from __future__ import annotations
import secrets
from typing import Optional, Generator
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.config import settings

__all__ = ["get_db", "require_operator"]


def require_operator(token: Optional[str]) -> None:
    if not token or not secrets.compare_digest(token, settings.OPERATOR_SECRET):
        raise HTTPException(401, "Invalid or missing operator secret.")
