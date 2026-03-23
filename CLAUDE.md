# Volleyball Scheduler — Claude Instructions

This file is loaded automatically by Claude Code at the start of every session.
It tells Claude how to work in this repository.

## Project overview

A full-stack volleyball game scheduling system.

- **Backend**: Python 3.9 + FastAPI + SQLAlchemy 2 + SQLite (`backend/`)
- **Web**: React 18 + Vite + Tailwind CSS (`web/`)
- **Mobile**: Expo (React Native) for Android & iOS (`mobile/`)

## Key documents

| Source | Purpose |
|--------|---------|
| https://bit.ly/3PSKZTa | Original requirements document (authoritative source) |
| `SPEC.md` | Plain-text transcription of the above — use this for quick reference |
| `DESIGN.md` | Architecture, data model, API reference, algorithm pseudocode (regenerate if missing) |

When starting a new feature, check the requirements URL or `SPEC.md` first.
If a requirement is not covered there, discuss with the user before adding it.

## Running the backend

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload          # http://localhost:8000
```

## Running tests

```bash
cd backend
PYTHONPATH=. pytest tests/test_scenarios.py -v
```

All 64 scenario tests must pass before merging any change to the scheduler or
models.

## Python conventions

- Python 3.9 — always add `from __future__ import annotations` at the top of
  every file and use `Optional[T]` / `List[T]` from `typing` (not `T | None`
  or `list[T]`).
- SQLAlchemy 2 declarative style with `Mapped[]` columns.
- After inserting rows via FK (not ORM relationship), call `db.expire(obj)` to
  force lazy-reload of relationship collections.

## Security rules

- `X-Player-Token` header is required for all state-mutating player actions
  (queue join/leave, confirm). Check with `secrets.compare_digest`.
- `X-Operator-Secret` header is required for game start/end.
- Twilio webhook must validate `X-Twilio-Signature` when `STUB_SMS=false`.
- Never widen `ALLOWED_ORIGINS` to `"*"` in production.

## Test fixture note

`make_player()` in `tests/test_scenarios.py` must set `is_verified=True` and
a non-null `secret_token` so unit tests bypass the verification/auth layer.

## Environment variables (`.env`)

```
DATABASE_URL=sqlite:///./volleyball.db
MAX_PLAYERS=12
CONFIRM_TIMEOUT_SECONDS=300
VERIFICATION_EXPIRES_MINUTES=15
STUB_SMS=true
STUB_PUSH=true
STUB_EMAIL=true
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:19006
OPERATOR_SECRET=change-me-in-production
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_FROM_NUMBER=
BASE_URL=http://localhost:8000
```
