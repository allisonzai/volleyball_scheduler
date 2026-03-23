from __future__ import annotations
import logging
import smtplib
import ssl
from email.mime.text import MIMEText
from app.config import settings

logger = logging.getLogger(__name__)


def send_verification_email(to_address: str, display_name: str, code: str) -> None:
    """Send a verification code to the player's email address via Gmail SMTP."""
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

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = settings.GMAIL_ADDRESS
    msg["To"] = to_address

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(settings.GMAIL_ADDRESS, settings.GMAIL_APP_PASSWORD)
        server.sendmail(settings.GMAIL_ADDRESS, to_address, msg.as_string())

    logger.info(f"Verification email sent to {to_address}")
