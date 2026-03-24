from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from app.models import player, game, game_slot, waiting_list, event_log  # noqa: F401
    Base.metadata.create_all(bind=engine)
    _migrate_db()


def _migrate_db() -> None:
    """Apply any additive schema migrations that create_all won't handle
    (i.e. new columns on existing tables)."""
    from sqlalchemy import text
    migrations = [
        "ALTER TABLE games ADD COLUMN game_number INTEGER",
        "ALTER TABLE players ADD COLUMN password_hash VARCHAR(256) NOT NULL DEFAULT ''",
        "ALTER TABLE players ADD COLUMN verification_code VARCHAR(6)",
        "ALTER TABLE players ADD COLUMN verification_expires_at DATETIME",
    ]
    with engine.connect() as conn:
        for stmt in migrations:
            try:
                conn.execute(text(stmt))
                conn.commit()
            except Exception:
                pass  # column already exists
