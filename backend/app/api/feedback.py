from __future__ import annotations
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException

from app.services.email import send_feedback_email

router = APIRouter(prefix="/api/feedback", tags=["feedback"])


class FeedbackIn(BaseModel):
    sender: str
    subject: str
    content: str


@router.post("", status_code=204)
def submit_feedback(body: FeedbackIn) -> None:
    if not body.sender.strip() or not body.subject.strip() or not body.content.strip():
        raise HTTPException(400, "All fields are required.")
    try:
        send_feedback_email(body.sender.strip(), body.subject.strip(), body.content.strip())
    except RuntimeError as e:
        raise HTTPException(502, str(e))
