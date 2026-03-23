from __future__ import annotations
import logging
import httpx
from app.config import settings

logger = logging.getLogger(__name__)

SENDGRID_URL = "https://api.sendgrid.com/v3/mail/send"


def send_verification_email(to_address: str, display_name: str, code: str) -> None:
    """Send a verification code via SendGrid's HTTP API."""
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
        "personalizations": [{"to": [{"email": to_address}]}],
        "from": {"email": settings.EMAIL_FROM, "name": "Volleyball Scheduler"},
        "subject": subject,
        "content": [{"type": "text/plain", "value": body}],
    }
    headers = {
        "Authorization": f"Bearer {settings.SENDGRID_API_KEY}",
        "Content-Type": "application/json",
    }

    response = httpx.post(SENDGRID_URL, json=payload, headers=headers, timeout=10)
    if response.status_code not in (200, 202):
        logger.error(f"SendGrid error {response.status_code}: {response.text}")
        raise RuntimeError(f"Failed to send verification email (status {response.status_code})")

    logger.info(f"Verification email sent to {to_address}")
