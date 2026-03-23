from __future__ import annotations
from typing import Optional
import logging
import httpx
from app.config import settings

logger = logging.getLogger(__name__)

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"


def send_push(token: str, title: str, body: str, data: Optional[dict] = None) -> None:
    """Send an Expo push notification. Uses stub mode when STUB_PUSH=true."""
    if settings.STUB_PUSH:
        logger.info(f"[PUSH STUB] Token: {token} | Title: {title} | Body: {body} | Data: {data}")
        return

    payload = {
        "to": token,
        "title": title,
        "body": body,
        "sound": "default",
    }
    if data:
        payload["data"] = data

    response = httpx.post(EXPO_PUSH_URL, json=payload, timeout=10)
    response.raise_for_status()
    logger.info(f"Push notification sent to {token}")
