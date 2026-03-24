from __future__ import annotations
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, Response

from app.services.email import send_feedback_email

router = APIRouter(prefix="/api/feedback", tags=["feedback"])


class FeedbackIn(BaseModel):
    sender: str
    subject: str
    content: str


@router.post("", status_code=204, response_class=Response)
def submit_feedback(body: FeedbackIn) -> Response:
    sender, subject, content = body.sender.strip(), body.subject.strip(), body.content.strip()
    if not sender or not subject or not content:
        raise HTTPException(400, "All fields are required.")
    try:
        send_feedback_email(sender, subject, content)
    except RuntimeError as e:
        raise HTTPException(502, str(e))
