import logging
from app.config import settings

logger = logging.getLogger(__name__)


def send_sms(to: str, body: str) -> None:
    """Send an SMS via Twilio. Uses stub mode when STUB_SMS=true."""
    if settings.STUB_SMS:
        logger.info(f"[SMS STUB] To: {to} | Message: {body}")
        return

    from twilio.rest import Client
    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    client.messages.create(to=to, from_=settings.SMS_FROM_NUMBER, body=body)
    logger.info(f"SMS sent to {to}")
