from __future__ import annotations
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr


class PlayerCreate(BaseModel):
    first_name: str
    last_name: str
    phone: str
    email: EmailStr
    password: str


class PlayerUpdate(BaseModel):
    expo_push_token: Optional[str] = None


class PlayerOut(BaseModel):
    id: int
    first_name: str
    last_name: str
    phone: str
    email: str
    display_name: str
    expo_push_token: Optional[str]
    is_verified: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class PlayerRegisterOut(PlayerOut):
    """Returned at registration and sign-in — includes the secret token."""
    secret_token: str


class SignInRequest(BaseModel):
    phone: str
    password: str


class VerificationRequest(BaseModel):
    channel: str = "email"  # "email" or "sms"


class VerificationSubmit(BaseModel):
    code: str
