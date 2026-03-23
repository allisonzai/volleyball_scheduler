# Volleyball Scheduler — Design Document

## Table of Contents

1. [Overview](#1-overview)
2. [Requirements](#2-requirements)
3. [System Architecture](#3-system-architecture)
4. [Data Model](#4-data-model)
5. [Scheduling Algorithm](#5-scheduling-algorithm)
6. [API Reference](#6-api-reference)
7. [Notification System](#7-notification-system)
8. [Frontend Design](#8-frontend-design)
9. [Real-time Updates](#9-real-time-updates)
10. [Configuration](#10-configuration)
11. [Testing Strategy](#11-testing-strategy)
12. [Deployment](#12-deployment)

---

## 1. Overview

Volleyball Scheduler is a full-stack application that manages recreational volleyball game scheduling and player queue rotation. Players register once, then sign up to play any number of times. The system ensures fair ordering via first-come-first-served queue management, handles player confirmations, and automatically rotates players between games.

### Components

| Component | Technology | Purpose |
|---|---|---|
| Backend API | Python 3.9 · FastAPI · SQLAlchemy 2.0 | Business logic, scheduling, persistence |
| Database | SQLite (file-based) | Player, game, and queue state |
| Web App | React 18 · Vite · Tailwind CSS | Browser interface |
| Mobile App | React Native · Expo | iOS and Android interface |
| SMS | Twilio (stubbed by default) | Confirmation notifications |
| Push Notifications | Expo Push API (stubbed by default) | In-app alerts |
| Email | Resend HTTP API (stubbed by default) | Future use; currently auto-verify skips email |
| Backend hosting | PythonAnywhere (free tier, WSGI) | Production backend |
| Frontend hosting | Vercel | Production web frontend |

---

## 2. Requirements

The following rules are taken directly from the specification.

| # | Rule |
|---|---|
| R1 | Every game can have at most 12 players. |
| R2 | Every player must sign up and receive a number assigned on a first-come-first-served basis. |
| R3 | If more than 12 players are present, the first 12 play and the rest wait. |
| R4 | Players who arrive while a game is ongoing join the waiting list. |
| R5 | When a game ends, court players rotate to the end of the waiting list. The next 12 in line play the following game. |
| R6 | If 12 or fewer players are present, no scheduling is needed — everyone plays immediately. |
| R7 | Any player may leave the waiting list at any time. |
| R8 | When a player is scheduled, they are notified and have up to 5 minutes (configurable) to respond. |
| R9 | Responding **yes** marks the player as playing. |
| R10 | Responding **no** removes the player from the current game and places them at the end of the waiting list. The next person is notified. |
| R11 | Responding **defer** places the player at the front of the waiting list. The next person is notified. |
| R12 | Confirmation can be sent by typing or clicking **yes**, **no**, or **defer**. |
| R13 | Players are displayed as "FirstName L" — duplicates are disambiguated by appending the last 4 digits of their phone number in brackets, e.g. `Alice J [4242]`. |
| R14 | Every player on the court and waiting list is shown alongside their signup number. |
| R7a | A confirmed player may leave an active game at any time. They are moved to the end of the waiting list and the next queued player is notified. |
| R7b | The operator may "Start Over" to cancel the active game and clear the waiting list. Player accounts are preserved. |

---

## 3. System Architecture

### 3.1 High-Level Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                          Clients                                │
│                                                                 │
│   ┌──────────────┐     ┌──────────────┐     ┌──────────────┐   │
│   │  Web Browser │     │  iOS Device  │     │ Android Dev. │   │
│   │  (React/Vite)│     │ (Expo Go /   │     │ (Expo Go /   │   │
│   │              │     │  Native App) │     │  Native App) │   │
│   └──────┬───────┘     └──────┬───────┘     └──────┬───────┘   │
└──────────┼────────────────────┼────────────────────┼───────────┘
           │ HTTP / SSE         │ HTTP / Push         │
           ▼                    ▼                     │
┌──────────────────────────────────────────────────────────────────┐
│                        Backend (FastAPI)                         │
│                                                                  │
│  ┌────────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐   │
│  │  /players  │  │  /queue   │  │  /games   │  │  /confirm │   │
│  └────────────┘  └───────────┘  └───────────┘  └───────────┘   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                  Scheduler Service                        │   │
│  │  assign_next_game · handle_confirmation · end_game       │   │
│  │  fill_slot · handle_timeout · queue management           │   │
│  └────────────────────────────┬─────────────────────────────┘   │
│           ┌────────────────────┤                                 │
│           ▼                    ▼                                 │
│  ┌─────────────────┐  ┌──────────────────────┐                 │
│  │  SQLite via     │  │  Notification Layer  │                 │
│  │  SQLAlchemy     │  │  SMS (Twilio)        │                 │
│  └─────────────────┘  │  Push (Expo)         │                 │
│                        └──────────────────────┘                 │
└──────────────────────────────────────────────────────────────────┘
           │ Inbound SMS
           ▼
    Twilio Webhook → POST /api/sms/webhook
```

### 3.2 Directory Structure

```
volleyball_scheduler/
├── backend/
│   ├── app/
│   ├── wsgi.py               # PythonAnywhere WSGI entry (lazy ASGIMiddleware)
│   ├── app/
│   │   ├── main.py               # App factory, CORS, init_db() at import time
│   │   ├── config.py             # Pydantic Settings (env vars)
│   │   ├── database.py           # SQLAlchemy engine, session, Base
│   │   ├── models/
│   │   │   ├── player.py         # Player ORM model
│   │   │   ├── game.py           # Game ORM model + GameStatus enum
│   │   │   ├── game_slot.py      # GameSlot ORM model + SlotStatus enum
│   │   │   └── waiting_list.py   # WaitingList ORM model
│   │   ├── schemas/
│   │   │   ├── player.py         # Pydantic request/response schemas
│   │   │   ├── game.py
│   │   │   └── queue.py
│   │   ├── api/
│   │   │   ├── players.py        # /api/players routes (incl. DELETE deregister)
│   │   │   ├── queue.py          # /api/queue routes
│   │   │   ├── games.py          # /api/games routes (incl. /reset, /{id}/leave)
│   │   │   ├── notifications.py  # /api/confirm + /api/sms/webhook
│   │   │   └── events.py         # /api/events (SSE — backend only; not used by web)
│   │   ├── services/
│   │   │   ├── scheduler.py      # Core scheduling engine (threading.Timer timeouts)
│   │   │   ├── display_name.py   # Display name generation + dedup
│   │   │   ├── notifications.py  # Orchestrates SMS + push
│   │   │   ├── sms.py            # Twilio adapter
│   │   │   ├── push.py           # Expo push adapter
│   │   │   ├── email.py          # Resend HTTP API adapter
│   │   │   └── password.py       # PBKDF2-SHA256 hash/verify
│   ├── tests/
│   │   └── test_scenarios.py     # 64 scenario-driven unit tests
│   ├── requirements.txt
│   └── .env.example
│
├── web/
│   ├── src/
│   │   ├── api/client.ts         # Axios wrapper for all API calls
│   │   ├── components/
│   │   │   ├── CourtView.tsx     # Active game + slot status
│   │   │   ├── WaitingListView.tsx
│   │   │   ├── ConfirmationBanner.tsx
│   │   │   ├── PastGamesView.tsx
│   │   │   ├── PlayerBadge.tsx
│   │   │   └── PlayerRegistration.tsx
│   │   ├── hooks/
│   │   │   ├── useGameState.ts   # 5-second polling hook (SSE removed for WSGI compat)
│   │   │   └── usePlayer.ts      # localStorage-persisted player
│   │   └── pages/Home.tsx        # Single-page layout
│   └── package.json
│
└── mobile/
    ├── app/
    │   ├── _layout.tsx           # Expo Router root
    │   ├── index.tsx             # Home screen
    │   ├── register.tsx          # Registration screen
    │   └── history.tsx           # Past games screen
    ├── components/               # RN equivalents of web components
    ├── services/
    │   ├── api.ts                # Same API surface as web client
    │   └── notifications.ts      # Expo push token registration
    └── package.json
```

---

## 4. Data Model

### 4.1 Entity Relationship Diagram

```
┌──────────────────────────────────────┐
│                Player                │
├──────────────────────────────────────┤
│ id              INT PK               │
│ first_name      VARCHAR(100)         │
│ last_name       VARCHAR(100)         │
│ phone           VARCHAR(20) UNIQUE   │
│ email           VARCHAR(200) UNIQUE  │
│ display_name    VARCHAR(150)         │
│ password_hash   VARCHAR(256)         │
│ is_verified     BOOLEAN default TRUE │
│ expo_push_token VARCHAR(200) NULL    │
│ created_at      DATETIME             │
└──────┬───────────────────────────────┘
       │ 1                         1
       │──────────────────────┐    │
       │                      ▼    ▼
       │          ┌─────────────────────────┐
       │          │       WaitingList        │
       │          ├─────────────────────────┤
       │          │ id            INT PK    │
       │          │ player_id     FK→Player │
       │          │ signup_number INT       │  ← assigned at join; never changes
       │          │ position      INT       │  ← resequenced after every mutation
       │          │ joined_at     DATETIME  │
       │          └─────────────────────────┘
       │
       │ 1         *
       ▼
┌─────────────────────────────────────────┐
│                GameSlot                  │
├─────────────────────────────────────────┤
│ id              INT PK                   │
│ game_id         FK → Game               │
│ player_id       FK → Player             │
│ position        INT   (court seat 1–12) │
│ status          VARCHAR(30)             │
│                   pending_confirmation  │
│                   confirmed             │
│                   declined              │
│                   timed_out             │
│                   withdrawn             │
│ notified_at     DATETIME NULL           │
│ responded_at    DATETIME NULL           │
└──────────────┬──────────────────────────┘
               │ *            1
               ▼
┌──────────────────────────────────────────┐
│                  Game                     │
├──────────────────────────────────────────┤
│ id           INT PK                      │
│ status       VARCHAR(20)                 │
│                open                      │
│                in_progress               │
│                finished                  │
│ max_players  INT (default 12)            │
│ started_at   DATETIME NULL               │
│ ended_at     DATETIME NULL               │
│ created_at   DATETIME                    │
└──────────────────────────────────────────┘
```

### 4.2 Key Invariants

| Invariant | Description |
|---|---|
| `WaitingList.player_id` is UNIQUE | A player appears at most once in the queue at any time. |
| `WaitingList.signup_number` is monotonically increasing | Assigned from a global counter; never changes after assignment. |
| `WaitingList.position` is compacted to `1..N` | Resequenced after every mutation (join, leave, defer). |
| A player has at most one slot per game | `fill_slot` excludes players who have any slot (any status) in the current game. |
| `GameSlot.position` values are unique within a game | Tracks physical court seat assignment. |

### 4.3 Game Status Transitions

```
         assign_next_game()
NONE ──────────────────────────► OPEN
                                   │
         all slots confirmed        │  or queue exhausted (fill_slot returns False)
           ──────────────────────► IN_PROGRESS
                                       │
                  end_game()           │
                    ──────────────────► FINISHED
```

### 4.4 Slot Status Transitions

```
          notify_player()
(created) ──────────────────► PENDING_CONFIRMATION
                                      │
                    ┌─────────────────┼──────────────────┐
                    │ yes             │ no / defer        │ timeout
                    ▼                 ▼                   ▼
               CONFIRMED          DECLINED           TIMED_OUT
                    │
                    │ leave_game()
                    ▼
               WITHDRAWN
```

---

## 5. Scheduling Algorithm

All scheduling logic is in `backend/app/services/scheduler.py`.

### 5.1 Starting a Game: `assign_next_game(db)`

Called by the operator via `POST /api/games/start`, and automatically after each game ends.

```
queue = get_queue(db)                          # ordered by position ASC

if queue is empty:
    return None

game = create Game(status=OPEN)

if len(queue) ≤ MAX_PLAYERS:
    # R6: everyone plays immediately — no confirmation needed
    for each player in queue:
        create GameSlot(status=CONFIRMED)
    clear waiting list
    game.status = IN_PROGRESS
    game.started_at = now()
else:
    # R3: pull first MAX_PLAYERS, notify each
    for each player in queue[:MAX_PLAYERS]:
        remove from queue
        create GameSlot(status=PENDING_CONFIRMATION)
        send notification (SMS + push)
        schedule 5-minute timeout

expire game (force SQLAlchemy to reload .slots relationship)
return game
```

### 5.2 Filling an Open Slot: `fill_slot(db, game)`

Called whenever a slot becomes vacant (no/defer/timeout).

```
already_slotted = {s.player_id for s in game.slots}
    # includes ALL statuses — prevents a player getting two slots in one game

next_player = first in queue WHERE player_id NOT IN already_slotted

if next_player is None:
    # Queue exhausted — start game with whoever confirmed so far
    if _confirmed_count(game) > 0 and game.status == OPEN:
        game.status = IN_PROGRESS
        game.started_at = now()
    return False

remove next_player from queue
create GameSlot(status=PENDING_CONFIRMATION) for next_player
send notification
schedule timeout
expire game
return True
```

The `already_slotted` check is the key invariant that prevents a player from being drawn twice for the same game — even if they were declined, timed out, or deferred and placed back at the front of the queue.

### 5.3 Handling a Confirmation: `handle_confirmation(player_id, game_id, response, db)`

```
validate response ∈ {"yes", "no", "defer"} (case-insensitive, stripped)
load slot; if not PENDING_CONFIRMATION, return silently

cancel timeout task for (player_id, game_id)
slot.responded_at = now()

if response == "yes":
    slot.status = CONFIRMED
    if _pending_count(game) == 0 and _confirmed_count(game) > 0:
        game.status = IN_PROGRESS

if response == "no":
    slot.status = DECLINED
    append player to END of queue         # R10
    fill_slot(game)                       # notify next person

if response == "defer":
    slot.status = DECLINED
    fill_slot(game)                       # notify next person FIRST  ← key ordering
    prepend player to FRONT of queue      # R11 — holds position for next available slot
```

**Why `fill_slot` before `prepend` for defer:** If we prepended first, `fill_slot` would immediately re-draw the deferred player (they'd be at position 1). Calling `fill_slot` first consumes the next person from the queue _before_ the deferred player is added, so they hold front position for the _next_ available opportunity without being immediately re-notified for the same game.

### 5.4 Handling a Timeout: `handle_timeout(player_id, game_id, db)`

```
if slot.status != PENDING_CONFIRMATION:
    return   # already responded; ignore late fire

slot.status = TIMED_OUT
append player to END of queue
fill_slot(game)
```

### 5.5 Ending a Game: `end_game(game_id, db)`

```
game.status = FINISHED
game.ended_at = now()

cancel all outstanding timeouts for this game

confirmed_players = [s for s in game.slots if s.status == CONFIRMED]
                    sorted by court position

for each confirmed player (in seat order):
    append to END of queue         # R5

# No auto-start — operator must press "Start New Game" manually
```

### 5.6 Player Leaves Mid-Game: `leave_game(player_id, game_id, db)`

Called when a confirmed player voluntarily exits an active game (R7a).

```
load slot for (player_id, game_id)
if slot not found or slot.status != CONFIRMED:
    raise LookupError

load game; if game.status not in (OPEN, IN_PROGRESS):
    raise LookupError

slot.status = WITHDRAWN
slot.responded_at = now()

append player to END of queue
fill_slot(db, game)                # notify next waiting player
```

### 5.7 Reset All: `reset_all(db)`

Operator-triggered "Start Over" that wipes all game history and queue (R7b).
Deleting game records resets the SQLite ID counter so the next game starts at #1.

```
cancel all pending timeout timers
_timeout_tasks.clear()

DELETE all GameSlot rows      # FK order: slots before games
DELETE all Game rows          # resets SQLite ID sequence to 1
DELETE all WaitingList rows
# Player accounts are NOT deleted
```

### 5.8 Queue Position Management

The `WaitingList` table uses two independent numbers per entry:

| Field | Meaning | Mutability |
|---|---|---|
| `signup_number` | Global join order (1, 2, 3…) | **Never changes.** Shown in UI as the player's permanent number. |
| `position` | Current queue rank (1 = next to play) | **Resequenced** to compact integers after every mutation. |

After every structural change (add, remove, prepend), `_resequence()` renumbers all remaining entries as `1, 2, 3, …N` to prevent gaps.

---

## 6. API Reference

### Players

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/api/players` | None | Register a new player. Returns 400 if phone or email already registered. Players are auto-verified. |
| `POST` | `/api/players/signin` | None | Sign in with phone + password. Returns player object with secret token. |
| `GET` | `/api/players/{id}` | None | Get a player's profile. |
| `DELETE` | `/api/players/{id}` | `X-Player-Token` | Permanently deregister. Returns 400 if player has active game slot. |
| `PATCH` | `/api/players/{id}/push-token` | None | Update the player's Expo push token. |

**Register request body:**
```json
{
  "first_name": "Alice",
  "last_name": "Smith",
  "phone": "+12125551234",
  "email": "alice@example.com",
  "password": "secret123"
}
```

**Sign-in request body:**
```json
{
  "phone": "+12125551234",
  "password": "secret123"
}
```

### Queue

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/api/queue` | None | Return the waiting list ordered by position. |
| `POST` | `/api/queue/join` | `X-Player-Token` | Add a player to the end of the queue. Body: `{"player_id": 1}`. |
| `DELETE` | `/api/queue/{player_id}` | `X-Player-Token` | Remove a player from the queue. |

**Queue entry response:**
```json
{
  "player_id": 3,
  "display_name": "Alice S",
  "signup_number": 3,
  "position": 1,
  "joined_at": "2026-03-22T10:00:00"
}
```

### Games

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/api/games/current` | None | Return the active game (OPEN or IN_PROGRESS), or `null`. |
| `GET` | `/api/games` | None | List all games. Optional `?status=` filter. |
| `GET` | `/api/games/{id}` | None | Get a specific game with all its slots. |
| `POST` | `/api/games/start` | `X-Operator-Secret` | Create and populate the next game from the queue. |
| `POST` | `/api/games/{id}/end` | `X-Operator-Secret` | Mark a game finished and trigger rotation. |
| `POST` | `/api/games/reset` | `X-Operator-Secret` | Cancel active game and clear waiting list (Start Over). |
| `POST` | `/api/games/{id}/leave` | `X-Player-Token` | Confirmed player leaves an active game mid-play. |

**Game response:**
```json
{
  "id": 1,
  "status": "in_progress",
  "max_players": 12,
  "started_at": "2026-03-22T10:05:00",
  "ended_at": null,
  "created_at": "2026-03-22T10:04:55",
  "slots": [
    {
      "id": 1,
      "player_id": 1,
      "position": 1,
      "status": "confirmed",
      "display_name": "Alice S",
      "signup_number": 1
    }
  ]
}
```

### Confirmation

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/confirm` | Submit a yes/no/defer response (from app button). |
| `POST` | `/api/sms/webhook` | Twilio inbound SMS webhook (from player text message). |

**Confirm request body:**
```json
{
  "player_id": 1,
  "game_id": 1,
  "response": "yes"
}
```

**SMS webhook:** Receives Twilio's standard `application/x-www-form-urlencoded` POST. Parses `From` (phone number) and `Body` (yes/no/defer). Returns TwiML `<Message>` response.

### Real-time Events

> **Note:** The SSE endpoint exists in the backend but is **not used** by the web frontend. PythonAnywhere's WSGI adapter (a2wsgi) would block a worker thread for every open SSE connection. The web app uses 5-second polling instead.

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/events` | Server-Sent Events stream (available but unused by current clients). |

Events are plain strings wrapped in the SSE `data:` format:
- `data: connected` — on initial connect
- `data: {"type": "game_update"}` — game state changed
- `data: {"type": "queue_update"}` — waiting list changed
- `: keepalive` — 30-second heartbeat to prevent proxy timeouts

---

## 7. Notification System

### 7.1 Channels

A player is notified via two channels simultaneously:

1. **SMS** — A text message containing the game number, confirmation deadline, and a link to the app. Sent via Twilio. Configurable with `STUB_SMS=true` for development (messages are logged instead of sent).

2. **Push notification** — A push alert sent to the player's registered Expo token. Sent via the Expo Push HTTP v2 API. Configurable with `STUB_PUSH=true` for development. The notification payload includes `game_id` and `player_id` in the `data` field so the mobile app can display the confirmation modal immediately on tap.

### 7.2 Inbound SMS Flow

```
Player's phone
     │  "YES"
     ▼
  Twilio
     │  POST /api/sms/webhook
     │  From: +12125551234
     │  Body: YES
     ▼
Backend
  1. Parse From and Body
  2. Look up Player by phone
  3. Find latest PENDING_CONFIRMATION slot for that player
  4. Call handle_confirmation(player_id, game_id, "yes", db)
  5. Return TwiML: "You're confirmed! Get ready to play."
```

### 7.3 Timeout Management

Confirmation timeouts are managed with `threading.Timer` (not asyncio). This is required for compatibility with PythonAnywhere's WSGI/uWSGI environment, where asyncio tasks do not survive the uWSGI fork process.

- When a slot is created, `_schedule_timeout(player_id, game_id)` is called.
- A `threading.Timer(CONFIRM_TIMEOUT_SECONDS, _timeout_job)` is started. The timer is daemon-mode so it doesn't prevent server shutdown.
- `_timeout_job` opens a new DB session, calls `handle_timeout()`, commits, then closes the session.
- Timers are stored in `_timeout_tasks: dict[(player_id, game_id), Timer]`.
- When a player responds (any answer), `_cancel_timeout(player_id, game_id)` calls `timer.cancel()`.
- `reset_all()` cancels all pending timers and clears `_timeout_tasks`.

**Limitation:** In-process timers do not survive a server restart. If the server restarts while a game is in confirmation, the 5-minute clocks reset. For production, these could be replaced with a persistent task queue (e.g., ARQ + Redis).

---

## 8. Frontend Design

### 8.1 Web Application

Built with React 18, Vite, and Tailwind CSS. Single-page application served on port 5173 in development, with a Vite proxy forwarding `/api` requests to the backend on port 8000.

#### Page Layout

```
┌────────────────────────────────────┐
│  🏐 Volleyball Scheduler     Alice S. │  ← Header (sticky)
├────────────────────────────────────┤
│                                    │
│  ┌─────────────────────────────┐   │
│  │  🏐 You're up for Game #3!  │   │  ← Confirmation banner
│  │  [Yes] [No] [Defer]         │   │     (visible only when player
│  └─────────────────────────────┘   │      has a pending slot)
│                                    │
│  [ Live ] [ Past Games ]           │  ← Tab nav
│                                    │
│  ┌─────────────────────────────┐   │
│  │  Current Game #3            │   │
│  │  On Court (12/12)           │   │  ← CourtView
│  │  Alice S.  Bob J.  …        │   │
│  └─────────────────────────────┘   │
│                                    │
│  ┌─────────────────────────────┐   │
│  │  Waiting List (4)           │   │
│  │  1. Carol D.  [Leave]       │   │  ← WaitingListView
│  │  2. Dave M.                 │   │
│  └─────────────────────────────┘   │
│                                    │
│  [ Join Waiting List ]             │  ← Visible if player not in queue
│                                    │
│  ──── Operator Controls ────       │
│  [ Start New Game ]                │
│  [ End Game #3 ]                   │
│  [ Start Over ]                    │
└────────────────────────────────────┘
```

#### State Management

Player identity is stored in `localStorage` (via `usePlayer` hook) and persists across page reloads. No authentication is implemented; the app operates on a trusted local network model.

Live game state is fetched via the `useGameState` hook, which polls `/api/games/current` and `/api/queue` every 5 seconds. SSE was removed because PythonAnywhere's WSGI adapter would block one worker per open connection.

### 8.2 Mobile Application

Built with React Native and Expo, using Expo Router for file-based navigation. Shares the same API surface as the web app.

#### Screens

| Screen | File | Description |
|---|---|---|
| Home | `app/index.tsx` | Court view, queue, controls, confirmation modal |
| Register | `app/register.tsx` | One-time player registration form |
| History | `app/history.tsx` | Past games list |

#### Push Notification Flow

```
1. On first launch, request permission
2. Obtain Expo push token
3. POST token to PATCH /api/players/{id}/push-token
4. When notification arrives and player taps it:
   - Notification data includes {game_id, player_id}
   - ConfirmationModal pops up with Yes / No / Defer buttons
5. Response POSTed to POST /api/confirm
```

#### Differences from Web

| Concern | Web | Mobile |
|---|---|---|
| Player persistence | `localStorage` | `AsyncStorage` |
| Live updates | SSE + 5s polling | 5s polling (SSE not used) |
| Confirmation | Banner in page | Bottom-sheet modal |
| Leave queue | Inline "Leave" button | Destructive alert dialog |

---

## 9. Real-time Updates

### Current Architecture (Polling)

The web client polls every 5 seconds:

```
Browser
  every 5 s ──► GET /api/games/current
  every 5 s ──► GET /api/queue
```

SSE (`GET /api/events`) is implemented in the backend and the `broadcast_update` helper still fires on state changes, but **no web client subscribes to it** because PythonAnywhere's WSGI adapter would block a worker thread per open connection indefinitely.

### SSE Backend (Available, Unused by Web)

The SSE infrastructure remains in `app/api/events.py` and `scheduler.broadcast_update()`. It can be re-enabled for clients that run against a proper ASGI server (uvicorn direct, not behind a2wsgi):

```
State change
     │
     ▼
scheduler.broadcast_update("game_update")
     │
     ▼
_sse_subscribers: list[asyncio.Queue]
     │
     ├─── Queue for Client A ──► SSE stream ──► Browser A
     └─── …
```

### Mobile

The mobile app also uses 5-second polling (no SSE).

---

## 10. Configuration

All configuration is read from environment variables (or a `.env` file) via Pydantic `BaseSettings`.

**Backend (`.env`):**

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./volleyball.db` | SQLAlchemy database connection string |
| `MAX_PLAYERS` | `12` | Maximum players per game |
| `CONFIRM_TIMEOUT_SECONDS` | `300` | Confirmation window in seconds (5 minutes) |
| `OPERATOR_SECRET` | `change-me-in-production` | Secret key for operator-only endpoints |
| `ALLOWED_ORIGINS` | `http://localhost:5173,...` | Comma-separated CORS allowed origins |
| `STUB_SMS` | `true` | If true, log SMS messages instead of sending via Twilio |
| `STUB_PUSH` | `true` | If true, log push notifications instead of sending via Expo |
| `STUB_EMAIL` | `true` | If true, skip email sending (auto-verify makes this safe) |
| `TWILIO_ACCOUNT_SID` | *(empty)* | Twilio account SID (required when `STUB_SMS=false`) |
| `TWILIO_AUTH_TOKEN` | *(empty)* | Twilio auth token |
| `TWILIO_FROM_NUMBER` | *(empty)* | Twilio sender phone number (E.164 format) |
| `RESEND_API_KEY` | *(empty)* | Resend API key (required when `STUB_EMAIL=false`) |
| `EMAIL_FROM` | *(empty)* | Sender email address for Resend |
| `BASE_URL` | `http://localhost:8000` | Public-facing URL embedded in SMS messages |

**Web frontend (`.env` / Vercel env vars):**

| Variable | Default | Description |
|---|---|---|
| `VITE_API_URL` | *(empty — same origin)* | Backend base URL (set to PythonAnywhere URL in production) |
| `VITE_OPERATOR_SECRET` | `change-me-in-production` | Operator secret for the web operator controls |

**Mobile frontend:**

| Variable | Default | Description |
|---|---|---|
| `EXPO_PUBLIC_API_URL` | `http://localhost:8000` | Backend base URL used by the mobile app |

---

## 11. Testing Strategy

### 11.1 Test Scope

The test suite (`backend/tests/test_scenarios.py`) contains **78 unit tests** that cover every rule in the specification plus new features (leave game, reset, deregister). Tests run against an in-memory SQLite database with no network calls (notification services are stubbed) and timeouts triggered manually.

### 11.2 Test Structure

Each test class maps to one specification rule:

| Class | Requirement | Tests |
|---|---|---|
| `TestScenario1_MaxTwelvePlayers` | R1 — max 12 players | 2 |
| `TestScenario2_SignupNumbers` | R2 — first-come-first-served numbers | 3 |
| `TestScenario3_MoreThan12Players` | R3 — first 12 play, rest wait | 3 |
| `TestScenario4_NewArrivalsJoinWaitingList` | R4 — late arrivals join queue | 2 |
| `TestScenario5_GameRotation` | R5 — court rotation after game | 3 |
| `TestScenario6_AtMost12Players` | R6 — everyone plays if ≤12 | 6 |
| `TestScenario7_LeaveWaitingList` | R7 — leave queue at any time | 5 |
| `TestScenario8_ConfigurableTimeout` | R8 — 5-min configurable timeout | 5 |
| `TestScenario9_ConfirmYes` | R9 — yes marks as playing | 3 |
| `TestScenario10_ConfirmNo` | R10 — no → end of queue | 4 |
| `TestScenario11_ConfirmDefer` | R11 — defer → front of queue | 4 |
| `TestScenario12_ValidResponses` | R12 — case-insensitive responses | 11 |
| `TestScenario13_DisplayNames` | R13 — display name format (`FirstName L`, brackets) | 5 |
| `TestScenario14_SignupNumbersVisible` | R14 — signup numbers shown | 3 |
| `TestScenario15_LeaveGameMidPlay` | R7a — leave active game mid-play | 5 |
| `TestScenario16_ResetAll` | R7b — Start Over / reset | 5 |
| `TestScenario17_Deregister` | Registration spec — deregister rules | 4 |
| `TestEdgeCases` | Edge cases | 5 |

### 11.3 Running Tests

```bash
cd backend
source .venv/bin/activate
pytest tests/test_scenarios.py -v
```

### 11.4 Key Test Design Decisions

**In-memory database per test.** Each test receives a fresh SQLite in-memory database via the `db` fixture. This gives perfect isolation without file I/O overhead.

**Manual timeout triggering.** Since tests should not fire real `threading.Timer` callbacks, the `db` fixture calls `scheduler._timeout_tasks.clear()` before each test. Tests that verify timeout behaviour call `scheduler.handle_timeout()` directly, bypassing the timer entirely.

**Chain-of-declines edge case.** When all backup players decline, the game starts with only the confirmed players. The test verifies this by triggering a third decline when only one backup player exists, causing the queue to be exhausted and the game to start with one confirmed player.

---

## 12. Deployment

### 12.1 Backend (PythonAnywhere)

The production backend runs on **PythonAnywhere free tier** (WSGI only, no long-running async).

Key files:
- `backend/wsgi.py` — PythonAnywhere WSGI entry. Uses a lazy singleton pattern to initialise `a2wsgi.ASGIMiddleware` inside the first request, after uWSGI has forked worker processes. This avoids the background-thread-doesn't-survive-fork hang.
- `backend/app/main.py` — Calls `init_db()` at module import time (not in an asyncio lifespan hook).

```python
# wsgi.py — lazy init pattern
from app.main import app
_asgi = None

def application(environ, start_response):
    global _asgi
    if _asgi is None:
        from a2wsgi import ASGIMiddleware
        _asgi = ASGIMiddleware(app)
    return _asgi(environ, start_response)
```

**PythonAnywhere Web tab settings:**
- Source code: `/home/<user>/volleyball_scheduler/backend`
- Virtualenv: `/home/<user>/venv`
- WSGI file: points to `wsgi.py`

After code changes: `git pull` in the backend directory, then reload the web app via the PythonAnywhere Web tab.

**Local development:**
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### 12.2 Web App (Vercel)

The production frontend is deployed to **Vercel**:

- Root directory: `web/`
- Build command: `npm run build`
- Output directory: `dist/`
- `vercel.json` contains SPA rewrite rules

**Required Vercel environment variables:**
- `VITE_API_URL` — PythonAnywhere backend URL (e.g. `https://allisonzai.pythonanywhere.com`)
- `VITE_OPERATOR_SECRET` — operator secret (must match backend `OPERATOR_SECRET`)

**Local development:**
```bash
cd web
npm install
npm run dev   # Vite dev server on :5173
```

### 12.3 Mobile App

For development:
```bash
cd mobile
npm install
EXPO_PUBLIC_API_URL=http://<YOUR_LAN_IP>:8000 npx expo start
```

For production, build with EAS Build:
```bash
npx eas build --platform all
```

Live game updates on mobile use 5-second polling. If lower latency is needed, add SSE support via `react-native-sse` or WebSockets.

### 12.4 SMS (Twilio)

1. Create a Twilio account and purchase a phone number.
2. Set `STUB_SMS=false` and fill in the Twilio credentials in `.env`.
3. Configure the Twilio number's inbound webhook URL to `https://<BASE_URL>/api/sms/webhook`.
4. Ensure `BASE_URL` in `.env` matches the public hostname so reply links in SMS messages resolve correctly.

### 12.5 Push Notifications (Expo)

Push notifications work automatically via the Expo Push API when `STUB_PUSH=false`. No server-side credentials are required for the Expo service. For Firebase Cloud Messaging (Android) or APNs (iOS) direct delivery, configure the keys in the Expo EAS dashboard and rebuild the app.
