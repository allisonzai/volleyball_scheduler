from __future__ import annotations
import asyncio
import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.services.scheduler import subscribe_sse, unsubscribe_sse

router = APIRouter(tags=["events"])


@router.get("/api/events")
async def sse_events():
    """Server-Sent Events stream for real-time updates."""
    queue = subscribe_sse()

    async def generator():
        try:
            yield "data: connected\n\n"
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30)
                    yield f"data: {json.dumps({'type': event})}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            unsubscribe_sse(queue)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
