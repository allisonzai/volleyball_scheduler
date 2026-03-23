import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.api import players, queue, games, notifications, events
from app.services.scheduler import set_event_loop
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    set_event_loop(asyncio.get_event_loop())
    yield


app = FastAPI(title="Volleyball Scheduler", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(players.router)
app.include_router(queue.router)
app.include_router(games.router)
app.include_router(notifications.router)
app.include_router(events.router)


@app.get("/")
def root():
    return {"message": "Volleyball Scheduler API", "docs": "/docs"}
