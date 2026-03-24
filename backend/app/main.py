from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.api import players, queue, games, notifications, events, settings as settings_api, activity
from app.config import settings

app = FastAPI(title="Volleyball Scheduler", version="1.0.0")

# Init DB at import time so WSGI workers (forked from master) all have the
# schema ready without needing any async lifespan events.
init_db()

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
app.include_router(settings_api.router)
app.include_router(activity.router)


@app.get("/")
def root():
    return {"message": "Volleyball Scheduler API", "docs": "/docs"}
