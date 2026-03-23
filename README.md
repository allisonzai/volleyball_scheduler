# Volleyball Scheduler

A full-stack volleyball game scheduling system with a Python/FastAPI backend, React web frontend, and React Native mobile app (iOS + Android).

## Features

- Player registration (name, phone, email)
- First-come-first-served signup queue with permanent signup numbers
- Auto-scheduling: first 12 players are notified; game starts on confirmation
- **yes** — player confirmed, takes their spot
- **no** — player removed from game, moved to end of queue
- **defer** — player moved to front of queue, next person notified
- Configurable 5-minute confirmation timeout (no response → end of queue)
- Players can leave the waiting list at any time
- Display names: "FirstName L." — disambiguated with last 2 phone digits if duplicate
- SMS notifications via Twilio (stub mode by default)
- Push notifications via Expo (stub mode by default)
- Real-time updates via Server-Sent Events + 5s polling fallback
- Past game history

---

## Quick Start

### 1. Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # edit if needed
uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

### 2. Web App

```bash
cd web
npm install
npm run dev       # http://localhost:5173
```

### 3. Mobile App (Expo)

```bash
cd mobile
npm install
npx expo start    # scan QR with Expo Go app
```

For a physical device, set `EXPO_PUBLIC_API_URL` to your backend's LAN IP:
```bash
EXPO_PUBLIC_API_URL=http://192.168.1.100:8000 npx expo start
```

---

## Configuration

Edit `backend/.env`:

| Variable | Default | Description |
|---|---|---|
| `MAX_PLAYERS` | `12` | Max players per game |
| `CONFIRM_TIMEOUT_SECONDS` | `300` | Seconds to confirm (5 min) |
| `STUB_SMS` | `true` | Log SMS instead of sending |
| `STUB_PUSH` | `true` | Log push instead of sending |
| `TWILIO_ACCOUNT_SID` | — | Twilio credentials |
| `TWILIO_AUTH_TOKEN` | — | Twilio credentials |
| `TWILIO_FROM_NUMBER` | — | Your Twilio phone number |
| `BASE_URL` | `http://localhost:8000` | Public URL (for SMS links) |

---

## API Overview

| Method | Path | Description |
|---|---|---|
| POST | `/api/players` | Register a player |
| GET | `/api/players/{id}` | Get player profile |
| PATCH | `/api/players/{id}/push-token` | Update Expo push token |
| GET | `/api/queue` | Get waiting list (ordered) |
| POST | `/api/queue/join` | Join the waiting list |
| DELETE | `/api/queue/{player_id}` | Leave the waiting list |
| GET | `/api/games/current` | Current active game |
| GET | `/api/games` | List all games |
| POST | `/api/games/start` | Start a new game (operator) |
| POST | `/api/games/{id}/end` | End a game (operator) |
| POST | `/api/confirm` | Submit yes/no/defer (app) |
| POST | `/api/sms/webhook` | Twilio inbound SMS webhook |
| GET | `/api/events` | Server-Sent Events stream |

---

## Architecture

```
backend/        FastAPI + SQLite + SQLAlchemy
web/            React + Vite + Tailwind CSS
mobile/         React Native + Expo (iOS & Android)
```

### Scheduling Logic

1. Players join the waiting list (assigned a permanent signup number).
2. Operator clicks "Start New Game".
3. If ≤ 12 players: everyone is added directly, game starts immediately.
4. If > 12 players: first 12 are notified one by one via SMS + push.
5. Each player has 5 minutes to respond:
   - **yes** → confirmed for the game
   - **no** → moved to end of queue, next player notified
   - **defer** → moved to front of queue, next player notified
   - **no response** → treated as timeout, moved to end of queue
6. Game starts when all slots are resolved.
7. When the game ends, court players rotate to the end of the queue, and the next game is auto-scheduled.
