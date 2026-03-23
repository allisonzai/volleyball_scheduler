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
| R13 | Players are displayed as "FirstName L." — duplicates are disambiguated using the last digits of their phone number. |
| R14 | Every player on the court and waiting list is shown alongside their signup number. |

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
│   │   ├── main.py               # App factory, CORS, lifespan hook
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
│   │   │   ├── players.py        # /api/players routes
│   │   │   ├── queue.py          # /api/queue routes
│   │   │   ├── games.py          # /api/games routes
│   │   │   ├── notifications.py  # /api/confirm + /api/sms/webhook
│   │   │   └── events.py         # /api/events (SSE stream)
│   │   ├── services/
│   │   │   ├── scheduler.py      # Core scheduling engine
│   │   │   ├── display_name.py   # Display name generation + dedup
│   │   │   ├── notifications.py  # Orchestrates SMS + push
│   │   │   ├── sms.py            # Twilio adapter
│   │   │   └── push.py           # Expo push adapter
│   │   └── tasks/                # (reserved for future async workers)
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
│   │   │   ├── useGameState.ts   # SSE + polling hook
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

assign_next_game(db)               # auto-start next game from updated queue
```

### 5.6 Queue Position Management

The `WaitingList` table uses two independent numbers per entry:

| Field | Meaning | Mutability |
|---|---|---|
| `signup_number` | Global join order (1, 2, 3…) | **Never changes.** Shown in UI as the player's permanent number. |
| `position` | Current queue rank (1 = next to play) | **Resequenced** to compact integers after every mutation. |

After every structural change (add, remove, prepend), `_resequence()` renumbers all remaining entries as `1, 2, 3, …N` to prevent gaps.

---

## 6. API Reference

### Players

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/players` | Register a new player. Returns 400 if phone or email already registered. |
| `GET` | `/api/players/{id}` | Get a player's profile. |
| `PATCH` | `/api/players/{id}/push-token` | Update the player's Expo push token. |

**Register request body:**
```json
{
  "first_name": "Alice",
  "last_name": "Smith",
  "phone": "+12125551234",
  "email": "alice@example.com"
}
```

### Queue

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/queue` | Return the waiting list ordered by position. |
| `POST` | `/api/queue/join` | Add a player to the end of the queue. Body: `{"player_id": 1}`. |
| `DELETE` | `/api/queue/{player_id}` | Remove a player from the queue. |

**Queue entry response:**
```json
{
  "player_id": 3,
  "display_name": "Alice S.",
  "signup_number": 3,
  "position": 1,
  "joined_at": "2026-03-22T10:00:00"
}
```

### Games

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/games/current` | Return the active game (OPEN or IN_PROGRESS), or `null`. |
| `GET` | `/api/games` | List all games. Optional `?status=` filter. |
| `GET` | `/api/games/{id}` | Get a specific game with all its slots. |
| `POST` | `/api/games/start` | Operator: create and populate the next game from the queue. |
| `POST` | `/api/games/{id}/end` | Operator: mark a game finished and trigger rotation. |

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
      "display_name": "Alice S.",
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

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/events` | Server-Sent Events stream. |

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

Confirmation timeouts are managed as in-process async tasks:

- When a slot is created, `_schedule_timeout(player_id, game_id)` is called.
- The task runs `asyncio.sleep(CONFIRM_TIMEOUT_SECONDS)` then calls `handle_timeout()`.
- Tasks are stored in `_timeout_tasks: dict[(player_id, game_id), Future]`.
- When a player responds (any answer), `_cancel_timeout(player_id, game_id)` cancels the pending task.
- The main asyncio event loop is captured at startup via `set_event_loop()` so that synchronous FastAPI route handlers (which run in worker threads) can schedule coroutines via `asyncio.run_coroutine_threadsafe()`.

**Limitation:** In-process tasks do not survive a server restart. If the server restarts while a game is in confirmation, the 5-minute clocks reset. For production, these could be replaced with a persistent task queue (e.g., ARQ + Redis).

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
└────────────────────────────────────┘
```

#### State Management

Player identity is stored in `localStorage` (via `usePlayer` hook) and persists across page reloads. No authentication is implemented; the app operates on a trusted local network model.

Live game state is fetched via the `useGameState` hook, which:
1. Establishes an SSE connection to `/api/events`.
2. Calls `refresh()` on every received event.
3. Falls back to a 5-second polling interval if SSE is unavailable.

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

### Architecture

```
State change (join queue, confirm, end game, etc.)
         │
         ▼
  scheduler.broadcast_update("game_update")
         │
         ▼
  _sse_subscribers: list[asyncio.Queue]
         │
         ├─── Queue for Client A ──► SSE stream ──► Browser A
         ├─── Queue for Client B ──► SSE stream ──► Browser B
         └─── Queue for Client C ──► SSE stream ──► Browser C
```

Each connected browser or web client maintains a persistent HTTP connection to `GET /api/events`. Each connection subscribes an `asyncio.Queue(maxsize=100)` to the global `_sse_subscribers` list. When `broadcast_update` is called from any scheduler function, the event string is placed into every subscriber's queue. Each SSE generator coroutine reads from its queue and yields the event.

### Keepalive

A 30-second `asyncio.wait_for` timeout triggers a `": keepalive\n\n"` comment line (ignored by clients but prevents proxy connection timeouts).

### Client Behavior

On receiving any SSE event, the client calls `refresh()`, which re-fetches `/api/games/current` and `/api/queue` in parallel. The client does not parse event payloads — all updates are treated as a full-refresh trigger.

---

## 10. Configuration

All configuration is read from environment variables (or a `.env` file) via Pydantic `BaseSettings`.

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./volleyball.db` | SQLAlchemy database connection string |
| `MAX_PLAYERS` | `12` | Maximum players per game |
| `CONFIRM_TIMEOUT_SECONDS` | `300` | Confirmation window in seconds (5 minutes) |
| `STUB_SMS` | `true` | If true, log SMS messages instead of sending via Twilio |
| `STUB_PUSH` | `true` | If true, log push notifications instead of sending via Expo |
| `TWILIO_ACCOUNT_SID` | *(empty)* | Twilio account SID (required when `STUB_SMS=false`) |
| `TWILIO_AUTH_TOKEN` | *(empty)* | Twilio auth token |
| `TWILIO_FROM_NUMBER` | *(empty)* | Twilio sender phone number (E.164 format) |
| `BASE_URL` | `http://localhost:8000` | Public-facing URL embedded in SMS messages |

**Mobile frontend:**

| Variable | Default | Description |
|---|---|---|
| `EXPO_PUBLIC_API_URL` | `http://localhost:8000` | Backend base URL used by the mobile app |

---

## 11. Testing Strategy

### 11.1 Test Scope

The test suite (`backend/tests/test_scenarios.py`) contains **64 unit tests** that cover every rule in the specification. Tests run against an in-memory SQLite database, with no network calls (notification services are stubbed), and no asyncio event loop (timeouts are triggered manually).

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
| `TestScenario13_DisplayNames` | R13 — display name format | 5 |
| `TestScenario14_SignupNumbersVisible` | R14 — signup numbers shown | 3 |
| `TestEdgeCases` | Edge cases | 5 |

### 11.3 Running Tests

```bash
cd backend
source .venv/bin/activate
pytest tests/test_scenarios.py -v
```

### 11.4 Key Test Design Decisions

**In-memory database per test.** Each test receives a fresh SQLite in-memory database via the `db` fixture. This gives perfect isolation without file I/O overhead.

**Manual timeout triggering.** Since tests have no asyncio event loop, `_main_loop` is set to `None`, which disables automatic timeout scheduling. Tests that verify timeout behaviour call `scheduler.handle_timeout()` directly.

**Chain-of-declines edge case.** When all backup players decline, the game starts with only the confirmed players. The test verifies this by triggering a third decline when only one backup player exists, causing the queue to be exhausted and the game to start with one confirmed player.

---

## 12. Deployment

### 12.1 Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # edit as needed
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

For production, add a process manager (e.g., `systemd`, `supervisord`) and reverse proxy (e.g., nginx). The single SQLite file (`volleyball.db`) is created automatically on first run.

### 12.2 Web App

```bash
cd web
npm install
npm run build                 # outputs to dist/
```

Serve the `dist/` directory with any static file server (nginx, Caddy, etc.), or deploy to Netlify/Vercel. Set the API proxy origin to match the backend hostname.

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
