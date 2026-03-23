from __future__ import annotations
import logging
import httpx
from app.config import settings

logger = logging.getLogger(__name__)

RESEND_URL = "https://api.resend.com/emails"


def send_verification_email(to_address: str, display_name: str, code: str) -> None:
    """Send a verification code via Resend's HTTP API."""
    subject = "Volleyball Scheduler — verify your account"
    body = (
        f"Hi {display_name},\n\n"
        f"Your verification code is: {code}\n\n"
        f"It expires in {settings.VERIFICATION_EXPIRES_MINUTES} minutes.\n\n"
        f"If you did not request this, ignore this email."
    )

    if settings.STUB_EMAIL:
        logger.info(f"[STUB EMAIL] To: {to_address} | Code: {code}")
        return

    payload = {
        "from": settings.EMAIL_FROM,
        "to": [to_address],
        "subject": subject,
        "text": body,
    }
    headers = {
        "Authorization": f"Bearer {settings.RESEND_API_KEY}",
        "Content-Type": "application/json",
    }

    response = httpx.post(RESEND_URL, json=payload, headers=headers, timeout=10)
    if response.status_code not in (200, 201):
        logger.error(f"Resend error {response.status_code}: {response.text}")
        raise RuntimeError(f"Failed to send verification email (status {response.status_code})")

    logger.info(f"Verification email sent to {to_address}")
