# Volleyball Scheduler

A full-stack volleyball game scheduling system with a Python/FastAPI backend, React web frontend, and React Native mobile app (iOS + Android).

## Features

- Player registration (name, phone, email, password) with instant sign-in
- First-come-first-served signup queue with permanent signup numbers
- Auto-scheduling: first 12 players are notified; game starts on confirmation
- **yes** — player confirmed, takes their spot
- **no** — player removed from game, moved to end of queue; next eligible player notified
- **defer** — player swaps with the next person in the queue (goes to position 2)
- Configurable 5-minute confirmation timeout (no response → end of queue)
- Players can leave the waiting list, or defer to swap with the next person behind them
- Confirmed players can leave an active game (removed from queue entirely)
- Display names: `FirstName L` — disambiguated with last 4 phone digits in brackets if duplicate (e.g. `Alice J [4242]`)
- SMS notifications via Twilio (stub mode by default)
- Push notifications via Expo (stub mode by default)
- 5-second polling for live updates
- Past game history with optional clear
- Operator controls: Start New Game, End Game, Start Over, Clear History

---

## Production Deployment

| Component | Platform |
|---|---|
| Backend | PythonAnywhere (free tier, WSGI via a2wsgi) |
| Web frontend | Vercel |

### PythonAnywhere (backend)

1. Clone the repo into your PythonAnywhere home directory.
2. Create a virtualenv and install dependencies:
   ```bash
   python3 -m venv ~/venv
   source ~/venv/bin/activate
   pip install -r backend/requirements.txt
   ```
3. In the **Web** tab: set the WSGI file to `backend/wsgi.py`, set the virtualenv path.
4. Create `backend/.env` from the table below.
5. Click **Reload**.

### Vercel (web frontend)

1. Connect the GitHub repo; set **Root Directory** to `web/`.
2. Add environment variables (see table below).
3. Deploy.

---

## Local Development

### Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # edit if needed
uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

### Web App

```bash
cd web
npm install
npm run dev       # http://localhost:5173
```

### Mobile App (Expo)

```bash
cd mobile
npm install
EXPO_PUBLIC_API_URL=http://192.168.1.100:8000 npx expo start
```

---

## Configuration

### Backend (`backend/.env`)

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./volleyball.db` | SQLAlchemy connection string |
| `MAX_PLAYERS` | `12` | Max players per game |
| `CONFIRM_TIMEOUT_SECONDS` | `300` | Seconds to confirm (5 min) |
| `OPERATOR_SECRET` | `change-me-in-production` | Protects start/end/reset endpoints |
| `ALLOWED_ORIGINS` | `http://localhost:5173,...` | CORS allowed origins |
| `STUB_SMS` | `true` | Log SMS instead of sending |
| `STUB_PUSH` | `true` | Log push instead of sending |
| `STUB_EMAIL` | `true` | Log email instead of sending |
| `TWILIO_ACCOUNT_SID` | — | Twilio credentials (when `STUB_SMS=false`) |
| `TWILIO_AUTH_TOKEN` | — | Twilio credentials |
| `TWILIO_FROM_NUMBER` | — | Your Twilio phone number |
| `RESEND_API_KEY` | — | Resend API key (when `STUB_EMAIL=false`) |
| `BASE_URL` | `http://localhost:8000` | Public URL (for SMS links) |

### Web frontend (Vercel env vars or `web/.env`)

| Variable | Description |
|---|---|
| `VITE_API_URL` | Backend base URL (e.g. `https://yourname.pythonanywhere.com`) |
| `VITE_OPERATOR_SECRET` | Must match backend `OPERATOR_SECRET` |

---

## API Overview

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/players` | — | Register a player |
| POST | `/api/players/signin` | — | Sign in (phone + password) |
| GET | `/api/players/{id}` | — | Get player profile |
| DELETE | `/api/players/{id}` | Player token | Deregister (blocked if in active game) |
| PATCH | `/api/players/{id}/push-token` | — | Update Expo push token |
| GET | `/api/queue` | — | Get waiting list (ordered) |
| POST | `/api/queue/join` | Player token | Join the waiting list |
| DELETE | `/api/queue/{player_id}` | Player token | Leave the waiting list |
| POST | `/api/queue/{player_id}/defer` | Player token | Swap with the next person in the waiting list |
| GET | `/api/games/current` | — | Current active game |
| GET | `/api/games` | — | List all games |
| POST | `/api/games/start` | Operator secret | Start a new game |
| POST | `/api/games/{id}/end` | Operator secret | End a game |
| POST | `/api/games/{id}/leave` | Player token | Leave an active game mid-play |
| POST | `/api/games/reset` | Operator secret | Start Over (cancel game, clear queue) |
| DELETE | `/api/games/history` | Operator secret | Delete all finished game records |
| POST | `/api/confirm` | Player token | Submit yes/no/defer |
| POST | `/api/sms/webhook` | Twilio signature | Inbound SMS webhook |

---

## Scheduling Logic

1. Players join the waiting list (assigned a permanent signup number).
2. Operator clicks **Start New Game**.
3. If ≤ 12 players: everyone is confirmed immediately, game starts.
4. If > 12 players: first 12 are notified via SMS + push.
5. Each player has 5 minutes to respond:
   - **yes** → confirmed
   - **no** → moved to end of queue; next eligible player notified
   - **defer** → swaps to position 2 in queue; next eligible player notified
   - *(no response)* → timeout, moved to end of queue
6. Game starts when all pending slots are resolved.
7. When the game ends, confirmed court players rotate to the end of the queue.
8. Operator clicks **Start New Game** to begin the next round.

### Operator Controls

| Button | Effect |
|---|---|
| Start New Game | Creates next game from the queue |
| End Game #N | Marks game finished; rotates court players to queue |
| Start Over | Cancels active game, clears queue; history preserved |
| Clear History | Deletes all finished game records (in Past Games tab) |

---

## Running Tests

```bash
cd backend
PYTHONPATH=. pytest tests/test_scenarios.py -v
```

87 scenario-driven tests covering all spec requirements.
