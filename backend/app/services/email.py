from __future__ import annotations
import logging
import httpx
from app.config import settings

logger = logging.getLogger(__name__)

RESEND_URL = "https://api.resend.com/emails"


def _send_resend_email(payload: dict) -> None:
    headers = {
        "Authorization": f"Bearer {settings.RESEND_API_KEY}",
        "Content-Type": "application/json",
    }
    response = httpx.post(RESEND_URL, json=payload, headers=headers, timeout=10)
    if response.status_code not in (200, 201):
        logger.error(f"Resend error {response.status_code}: {response.text}")
        raise RuntimeError(f"Resend request failed (status {response.status_code})")


def send_verification_email(to_address: str, display_name: str, code: str) -> None:
    """Send a verification code via Resend's HTTP API."""
    if settings.STUB_EMAIL:
        logger.info(f"[STUB EMAIL] To: {to_address} | Code: {code}")
        return

    _send_resend_email({
        "from": settings.EMAIL_FROM,
        "to": [to_address],
        "subject": "Volleyball Scheduler — verify your account",
        "text": (
            f"Hi {display_name},\n\n"
            f"Your verification code is: {code}\n\n"
            f"It expires in {settings.VERIFICATION_EXPIRES_MINUTES} minutes.\n\n"
            f"If you did not request this, ignore this email."
        ),
    })
    logger.info(f"Verification email sent to {to_address}")


def send_feedback_email(sender: str, subject: str, content: str) -> None:
    """Forward a feedback submission to the configured FEEDBACK_TO address."""
    if not settings.FEEDBACK_TO:
        logger.warning("FEEDBACK_TO not configured — feedback dropped.")
        return

    if settings.STUB_EMAIL:
        logger.info(f"[STUB FEEDBACK] To: {settings.FEEDBACK_TO} | Subject: {subject} | From: {sender}")
        return

    _send_resend_email({
        "from": settings.EMAIL_FROM,
        "to": [settings.FEEDBACK_TO],
        "reply_to": sender,
        "subject": subject,
        "text": f"From: {sender}\n\n{content}",
    })
    logger.info(f"Feedback email forwarded to {settings.FEEDBACK_TO}")
