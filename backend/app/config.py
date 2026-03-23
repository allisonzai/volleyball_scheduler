from __future__ import annotations
from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./volleyball.db"
    MAX_PLAYERS: int = 12
    CONFIRM_TIMEOUT_SECONDS: int = 300  # 5 minutes
    VERIFICATION_EXPIRES_MINUTES: int = 15

    STUB_SMS: bool = True
    STUB_PUSH: bool = True
    STUB_EMAIL: bool = True

    # Gmail — used to send verification emails
    GMAIL_ADDRESS: str = "allisonazhang@gmail.com"
    GMAIL_APP_PASSWORD: str = ""  # Generate at myaccount.google.com > Security > App Passwords

    # SMS — Twilio credentials + your Google Voice / Twilio FROM number
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    SMS_FROM_NUMBER: str = "8588480458"  # Your Google Voice number (port to Twilio to send SMS)

    BASE_URL: str = "http://localhost:8000"

    # Comma-separated allowed CORS origins
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:19006"

    # Secret required in X-Operator-Secret header for game start/end
    OPERATOR_SECRET: str = "change-me-in-production"

    model_config = {"env_file": ".env"}

    def allowed_origins_list(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]


settings = Settings()
