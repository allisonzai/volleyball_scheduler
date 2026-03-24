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

Volleyball Scheduler is a full-stack application that manages recreational
volleyball game scheduling and player queue rotation. Players register once,
then sign up to play any number of times. The system ensures fair ordering via
first-come-first-served queue management, handles player confirmations, and
automatically rotates players between games.

### Components

| Component          | Technology                            | Purpose                                       |
| ------------------ | ------------------------------------- | --------------------------------------------- |
| Backend API        | Python 3.9 · FastAPI · SQLAlchemy 2.0 | Business logic, scheduling, persistence       |
| Database           | SQLite (file-based)                   | Player, game, and queue state                 |
| Web App            | React 18 · Vite · Tailwind CSS        | Browser interface                             |
| Mobile App         | React Native · Expo                   | iOS and Android interface                     |
| SMS                | Twilio (stubbed by default)           | Confirmation notifications                    |
| Push Notifications | Expo Push API (stubbed by default)    | In-app alerts                                 |
| Email              | Resend HTTP API (stubbed by default)  | Future use; currently auto-verify skips email |
| Backend hosting    | PythonAnywhere (free tier, WSGI)      | Production backend                            |
| Frontend hosting   | Vercel                                | Production web frontend                       |

---

## 2. Requirements

The following rules are taken directly from the specification.

| #   | Rule                                                                                                                                                                                                                                                                                                                                              |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| R1  | Every game can have at most 12 players.                                                                                                                                                                                                                                                                                                           |
| R2  | Every player must sign up and receive a number assigned on a first-come-first-served basis.                                                                                                                                                                                                                                                       |
| R3  | If more than 12 players are present, the first 12 play and the rest wait.                                                                                                                                                                                                                                                                         |
| R4  | Players who arrive while a game is ongoing join the waiting list.                                                                                                                                                                                                                                                                                 |
| R5  | When a game ends, court players rotate to the end of the waiting list. The next 12 in line play the following game.                                                                                                                                                                                                                               |
| R6  | Even when 12 or fewer players are present, each must still confirm before the game starts.                                                                                                                                                                                                                                                        |
| R7  | Any player may leave the waiting list at any time. A player in the waiting list may also defer to swap positions with the next person behind them.                                                                                                                                                                                                |
| R7a | A confirmed player may leave an active game at any time. They are removed from both the game and the waiting list entirely. The next queued player is notified.                                                                                                                                                                                   |
| R7b | The operator may "Start Over" to cancel the active game and clear the waiting list. Player accounts are preserved.                                                                                                                                                                                                                                |
| R8  | When a player is scheduled, they are notified and have up to 5 minutes (configurable) to respond.                                                                                                                                                                                                                                                 |
| R9  | Responding **yes** marks the player as playing.                                                                                                                                                                                                                                                                                                   |
| R10 | Responding **no** (or not responding within the timeout) removes the player from the current game and from the waiting list entirely. The **first** person in the waiting list who has not already deferred for the current game is notified as replacement.                                                                                      |
| R11 | Responding **defer** swaps the player with the **first** person in the waiting list who has not already deferred for the current game. That person fills the vacated slot; the deferred player is re-inserted into the queue immediately before the next player who has not yet had a slot in this game, preserving their original signup number. |
| R12 | Confirmation is done by clicking **yes**, **no**, or **defer** in the app.                                                                                                                                                                                                                                                                        |
| R13 | Players are displayed as "FirstName L" — duplicates are disambiguated by appending the last 4 digits of their phone number in brackets, e.g. `Alice J [4242]`.                                                                                                                                                                                    |
| R14 | Every player on the court and waiting list is shown alongside their signup number.                                                                                                                                                                                                                                                                |

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
│   │   │   ├── waiting_list.py   # WaitingList ORM model
│   │   │   └── event_log.py      # EventLog ORM model
│   │   ├── schemas/
│   │   │   ├── player.py         # Pydantic request/response schemas
│   │   │   ├── game.py
│   │   │   └── queue.py
│   │   ├── api/
│   │   │   ├── players.py        # /api/players routes (incl. DELETE deregister)
│   │   │   ├── queue.py          # /api/queue routes
│   │   │   ├── games.py          # /api/games routes (incl. /reset, /{id}/leave,
│   │   │   │                     #   /{id}/begin)
│   │   │   ├── notifications.py  # /api/confirm + /api/sms/webhook
│   │   │   ├── settings.py       # /api/settings GET + PATCH
│   │   │   ├── activity.py       # /api/activity (event log)
│   │   │   └── events.py         # /api/events (SSE — backend only; not used by web)
│   │   ├── services/
│   │   │   ├── scheduler.py      # Core scheduling engine (threading.Timer timeouts)
│   │   │   ├── event_logger.py   # log_event() helper — writes to event_logs table
│   │   │   ├── display_name.py   # Display name generation + dedup
│   │   │   ├── notifications.py  # Orchestrates SMS + push
│   │   │   ├── sms.py            # Twilio adapter
│   │   │   ├── push.py           # Expo push adapter
│   │   │   ├── email.py          # Resend HTTP API adapter
│   │   │   └── password.py       # PBKDF2-SHA256 hash/verify
│   ├── tests/
│   │   └── test_scenarios.py     # 95 scenario-driven unit tests
│   ├── requirements.txt
│   └── .env.example
│
├── web/
│   ├── src/
│   │   ├── api/client.ts         # Axios wrapper for all API calls
│   │   ├── components/
│   │   │   ├── CourtView.tsx         # Active game + slot status
│   │   │   ├── WaitingListView.tsx
│   │   │   ├── ConfirmationBanner.tsx
│   │   │   ├── PastGamesView.tsx
│   │   │   ├── ActivityView.tsx      # Event log timeline (Events tab)
│   │   │   ├── PlayerBadge.tsx
│   │   │   └── PlayerRegistration.tsx
│   │   ├── hooks/
│   │   │   ├── useGameState.ts   # 5-second polling hook; also fetches settings
│   │   │   └── usePlayer.ts      # localStorage-persisted player
│   │   └── pages/Home.tsx        # Single-page layout (Live / Past Games / Events tabs)
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
│ signup_number   INT NULL                │  ← copied from WaitingList at slot creation
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
│ game_number  INT NULL UNIQUE             │  ← assigned only when IN_PROGRESS
│ status       VARCHAR(20)                 │
│                open          (staging)   │
│                in_progress   (gaming)    │
│                finished                  │
│ max_players  INT (default 12)            │
│ started_at   DATETIME NULL               │
│ ended_at     DATETIME NULL               │
│ created_at   DATETIME                    │
└──────────────────────────────────────────┘

┌──────────────────────────────────────────┐
│               EventLog                    │
├──────────────────────────────────────────┤
│ id           INT PK                      │
│ event_type   VARCHAR(50)                 │
│ description  VARCHAR(500)               │
│ game_id      INT NULL                    │
│ game_number  INT NULL                    │
│ created_at   DATETIME                    │
└──────────────────────────────────────────┘
```

### 4.2 Key Invariants

| Invariant                                               | Description                                                                                                                                                                                                  |
| ------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `WaitingList.player_id` is UNIQUE                       | A player appears at most once in the queue at any time.                                                                                                                                                      |
| `WaitingList.signup_number` is monotonically increasing | Assigned from a global counter; resets to 1 after Start Over (queue cleared).                                                                                                                                |
| `WaitingList.position` is compacted to `1..N`           | Resequenced after every mutation (join, leave, defer).                                                                                                                                                       |
| `GameSlot.signup_number` is copied at slot creation     | Captured from the player's `WaitingList` entry before they are removed from the queue; persists for display in the game view and past games history.                                                         |
| A player has at most one active slot per game           | During live confirmation `fill_slot` excludes all-status slots. During batch fill (`allow_requeue=True`) only PENDING/CONFIRMED slots are excluded, so deferred players in the queue may receive a new slot. |
| `GameSlot.position` values are unique within a game     | Tracks physical court seat assignment.                                                                                                                                                                       |
| `Game.game_number` is NULL until IN_PROGRESS            | Assigned by `_begin_game()`. Cancelled staging sessions (never reached IN_PROGRESS) leave no gap in the game number sequence.                                                                                |

### 4.3 Game Status Transitions

```
         assign_next_game()
NONE ──────────────────────────► OPEN  (Staging — game_number is NULL)
                                   │
         _begin_game()             │  triggered by:
           ──────────────────────► IN_PROGRESS  (game_number assigned here)
                                   │
                                   │  _begin_game() is called when:
                                   │    • all slots confirmed (full house), OR
                                   │    • queue exhausted with ≥1 confirmed, OR
                                   │    • operator clicks "Begin Game" (force_start_game)
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

Called by the operator via `POST /api/games/start`. The operator must manually
trigger this after each game ends.

```
queue = get_queue(db)                          # ordered by position ASC

if queue is empty:
    return None

game = create Game(status=OPEN)

# Always notify every selected player and require confirmation (R6)
for each player in queue[:MAX_PLAYERS]:
    capture player.signup_number          # saved before queue removal
    remove from queue
    create GameSlot(status=PENDING_CONFIRMATION, signup_number=signup_number)
    send notification (SMS + push)
    schedule confirmation timeout

expire game (force SQLAlchemy to reload .slots relationship)
log_event("game_staged", ...)
return game
# game_number is NULL here; assigned later by _begin_game()
```

### 5.2 Filling an Open Slot: `fill_slot(db, game, allow_requeue=False)`

Called whenever a slot becomes vacant (no/defer/timeout/leave-mid-play).

`allow_requeue` controls which existing slots count as "already taken":

- `allow_requeue=False` (default — live confirmation phase): all statuses are
  excluded. A player who deferred and was re-inserted into the queue is not
  immediately re-drawn for the same game.
- `allow_requeue=True` (batch fill after all pending resolve): only
  PENDING_CONFIRMATION and CONFIRMED slots are excluded. A player who deferred
  earlier (DECLINED slot, back in the queue) is eligible to fill a remaining
  spot when the queue would otherwise be too small.

```
if allow_requeue:
    already_slotted = {s.player_id for s in game.slots
                       WHERE s.status IN (PENDING_CONFIRMATION, CONFIRMED)}
else:
    already_slotted = {s.player_id for s in game.slots}   # all statuses

next_player = first in queue WHERE player_id NOT IN already_slotted

if next_player is None:
    # Queue exhausted — start game with whoever confirmed so far
    if _confirmed_count(game) > 0 and game.status == OPEN:
        _begin_game(db, game)            # assigns game_number
    return False

# Snapshot existing pending slots BEFORE creating the new one
existing_pending = [s for s in game.slots WHERE s.status == PENDING_CONFIRMATION]

capture next_player.signup_number        # saved before queue removal
remove next_player from queue
new_slot = create GameSlot(PENDING_CONFIRMATION, signup_number)
send notification
schedule timeout (delay = CONFIRM_TIMEOUT_SECONDS)
expire game
log_event("player_filled", ...)

# If other pending slots exist, apply fill_wait so the new player
# gets (remaining_time + FILL_WAIT_SECONDS)
if existing_pending:
    _apply_fill_wait(db, game, new_slot, existing_pending)

return True
```

### 5.2a Fill-Wait: `_apply_fill_wait(db, game, new_slot, existing_pending)`

Called by `fill_slot` when replacing a player while other slots are still
pending confirmation.

```
earliest_notified_at = min(s.notified_at for s in existing_pending)
new_slot.notified_at = earliest_notified_at    # backdate to match others

CONFIRM_TIMEOUT_SECONDS += FILL_WAIT_SECONDS   # extend global setting

# Reschedule all pending timers (existing + new) with the extended timeout
for slot in existing_pending + [new_slot]:
    elapsed   = now() - slot.notified_at
    remaining = max(0, CONFIRM_TIMEOUT_SECONDS - elapsed)
    reschedule_timeout(slot.player_id, game.id, delay=remaining)
```

Result: every pending player's client-side formula
`CONFIRM_TIMEOUT_SECONDS − (now − notified_at)` yields
`old_remaining + FILL_WAIT_SECONDS`. Not applied during batch fill
(no pending slots exist at that point).

### 5.2b Begin Game: `force_start_game(game_id, db)`

Operator-triggered early transition from OPEN → IN_PROGRESS.

```
game = load Game(game_id); assert status == OPEN
if _confirmed_count(game) == 0:
    raise ValueError  # nothing to start

for slot in game.slots WHERE status == PENDING_CONFIRMATION:
    cancel_timeout(slot.player_id, game_id)
    slot.status = DECLINED
    remove_from_queue(slot.player_id)

_begin_game(db, game)    # assigns game_number, sets started_at
log_event("game_force_begun", ...)
```


### 5.3 Handling a Confirmation: `handle_confirmation(player_id, game_id, response, db)`

```
validate response ∈ {"yes", "no", "defer"} (case-insensitive, stripped)
load slot; if not PENDING_CONFIRMATION, return silently

cancel timeout task for (player_id, game_id)
slot.responded_at = now()

if response == "yes":
    slot.status = CONFIRMED
    _try_fill_open_slots(db, game)        # may start game or batch-fill if all pending resolved

if response == "no":
    slot.status = DECLINED
    remove player from queue entirely     # R10 — they leave the system
    _try_fill_open_slots(db, game)        # batch-fill once all pending resolve

if response == "defer":
    slot.status = DECLINED
    fill_slot(game)                             # promote first eligible queue player FIRST
    re-insert player before first eligible      # R11 — preserves original signup_number
```

**`_try_fill_open_slots(db, game)` — batch fill logic:**

Called by both "yes" and "no"/"timeout" paths after each slot resolves.

```
if pending_count > 0:
    return  # still waiting for outstanding responses

needed = max_players - confirmed_count

if needed <= 0:
    game.status → IN_PROGRESS   # full house

else:
    for _ in range(needed):
        if not fill_slot(game, allow_requeue=True):
            break               # queue exhausted; fill_slot starts game if confirmed > 0
```

Key design notes:

- The `confirmed == 0` early-return was intentionally **removed**. If every
  player in the initial group times out, batch fill still runs so queue players
  get their turn. The game starts once at least one of them confirms. If the
  queue is also empty and confirmed = 0, the game remains OPEN until the
  operator clicks Start Over.
- `allow_requeue=True` is passed so deferred players re-inserted into the queue
  are eligible during batch fill. Without this, a deferred player's DECLINED
  slot would permanently block them even when they are the only person left in
  the queue.

---

**Why `fill_slot` before re-insert for defer:** `fill_slot` removes and promotes
the first eligible player, updating `game.slots`. Only after that is
`already_slotted` rebuilt so the re-insert function can correctly identify which
queue entries have already had a slot in this game. The deferred player is
placed immediately before the first remaining queue entry that has no slot in
this game — i.e., right after any players who have already deferred (and
therefore already appear in `already_slotted`). Their original `signup_number`
is carried over from their `GameSlot` record.

### 5.4 Handling a Timeout: `handle_timeout(player_id, game_id, db)`

No response within the timeout window is treated identically to "no".

```
if slot.status != PENDING_CONFIRMATION:
    return   # already responded; ignore late fire

handle_confirmation(player_id, game_id, "no", db)
# → slot.status = DECLINED, player removed from queue, _try_fill_open_slots called
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

remove player from queue entirely  # R7a: they leave both game and waiting list
fill_slot(db, game)                # notify next waiting player
```

### 5.7 Reset All: `reset_all(db)`

Operator-triggered "Start Over" (R7b). Cancels the active game and clears the
waiting list. Game **history is preserved** (finished games remain in Past
Games). Player accounts are not deleted.

```
cancel all pending timeout timers
_timeout_tasks.clear()

mark active game(s) as FINISHED
DELETE all WaitingList rows
# Game records and Player accounts are NOT deleted
```

### 5.8a Clear History: `clear_history(db)`

Deletes all FINISHED game records and their slots. Because SQLAlchemy does not
use `AUTOINCREMENT`, deleting all games resets the SQLite ID counter so the next
game starts at #1.

```
finished_ids = [g.id for g in FINISHED games]
DELETE GameSlot rows where game_id IN finished_ids   # FK order
DELETE Game rows where id IN finished_ids
# Active game, queue, and player accounts are NOT touched
```

### 5.9 Queue Defer: `defer_in_queue(player_id, db)`

Waiting-list players can swap positions with the person immediately behind them
(R7).

```
entry = get WaitingList entry for player_id
next_entry = first entry WHERE position > entry.position ORDER BY position

if next_entry is None:
    raise ValueError("Already last in queue")

swap entry.position ↔ next_entry.position
resequence (compact positions to 1..N)
```

### 5.10 Queue Position Management

The `WaitingList` table uses two independent numbers per entry:

| Field           | Meaning                                                                     | Mutability                                                                          |
| --------------- | --------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| `signup_number` | Queue join order for this session (1, 2, 3…). Resets to 1 after Start Over. | **Never changes** once assigned. Shown in UI as the player's number for this round. |
| `position`      | Current queue rank (1 = next to play)                                       | **Resequenced** to compact integers after every mutation.                           |

When a player moves from the queue into a game slot, their `signup_number` is
copied onto the `GameSlot` record **before** the `WaitingList` row is deleted.
This ensures the number is available for display in the court view and past
games history even after the player is no longer in the queue.

When a player **defers** and is re-inserted into the queue, their
`signup_number` is read back from their `GameSlot` record and written onto the
new `WaitingList` entry. This preserves the original number — a defer does not
cause a player to receive a new, higher number.

After every structural change (add, remove, prepend), `_resequence()` renumbers
all remaining entries as `1, 2, 3, …N` to prevent gaps.

---

## 6. API Reference

### Players

| Method   | Path                           | Auth             | Description                                                                                         |
| -------- | ------------------------------ | ---------------- | --------------------------------------------------------------------------------------------------- |
| `POST`   | `/api/players`                 | None             | Register a new player. Returns 400 if phone or email already registered. Players are auto-verified. |
| `POST`   | `/api/players/signin`          | None             | Sign in with phone + password. Returns player object with secret token.                             |
| `GET`    | `/api/players/{id}`            | None             | Get a player's profile.                                                                             |
| `DELETE` | `/api/players/{id}`            | `X-Player-Token` | Permanently deregister. Returns 400 if player has active game slot.                                 |
| `PATCH`  | `/api/players/{id}/push-token` | None             | Update the player's Expo push token.                                                                |

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

| Method   | Path                           | Auth             | Description                                                                                 |
| -------- | ------------------------------ | ---------------- | ------------------------------------------------------------------------------------------- |
| `GET`    | `/api/queue`                   | None             | Return the waiting list ordered by position.                                                |
| `POST`   | `/api/queue/join`              | `X-Player-Token` | Add a player to the end of the queue. Body: `{"player_id": 1}`.                             |
| `DELETE` | `/api/queue/{player_id}`       | `X-Player-Token` | Remove a player from the queue.                                                             |
| `POST`   | `/api/queue/{player_id}/defer` | `X-Player-Token` | Swap the player with the next person behind them in the queue. Returns 400 if already last. |

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

| Method   | Path                    | Auth                | Description                                                                    |
| -------- | ----------------------- | ------------------- | ------------------------------------------------------------------------------ |
| `GET`    | `/api/games/current`    | None                | Return the active game (OPEN or IN_PROGRESS), or `null`.                       |
| `GET`    | `/api/games`            | None                | List all games. Optional `?status=` filter.                                    |
| `GET`    | `/api/games/{id}`       | None                | Get a specific game with all its slots.                                        |
| `POST`   | `/api/games/start`        | `X-Operator-Secret` | Create and populate the next game (staging phase).                               |
| `POST`   | `/api/games/{id}/begin`   | `X-Operator-Secret` | Force-start: cancel pending slots, transition to IN_PROGRESS.                    |
| `POST`   | `/api/games/{id}/end`     | `X-Operator-Secret` | Mark a game finished and trigger rotation.                                       |
| `POST`   | `/api/games/reset`        | `X-Operator-Secret` | Cancel active game and clear waiting list (Start Over). History preserved.       |
| `DELETE` | `/api/games/history`      | `X-Operator-Secret` | Delete all finished game records and reset game ID sequence.                     |
| `POST`   | `/api/games/{id}/leave`   | `X-Player-Token`    | Confirmed player leaves an active game mid-play (removed from queue entirely).   |

**Game response:**

```json
{
  "id": 7,
  "game_number": 3,
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
      "signup_number": 1,
      "notified_at": "2026-03-22T10:04:56"
    }
  ]
}
```

`game_number` is `null` during staging and assigned when the game enters
`in_progress`. The internal `id` is always present but not shown to users.

### Settings

| Method  | Path             | Auth                | Description                          |
| ------- | ---------------- | ------------------- | ------------------------------------ |
| `GET`   | `/api/settings`  | None                | Return current confirm_timeout_seconds, fill_wait_seconds, max_players. |
| `PATCH` | `/api/settings`  | `X-Operator-Secret` | Update confirm_timeout_seconds and/or fill_wait_seconds. In-flight timers are rescheduled immediately. |

### Activity Log

| Method | Path            | Auth | Description                                          |
| ------ | --------------- | ---- | ---------------------------------------------------- |
| `GET`  | `/api/activity` | None | Return event log entries, newest first. `?limit=200` |

**Activity entry:**

```json
{
  "id": 42,
  "event_type": "player_confirmed",
  "description": "Alice S confirmed.",
  "game_id": 7,
  "game_number": 3,
  "created_at": "2026-03-22T10:05:30"
}
```

**Event types:** `game_staged`, `game_begun`, `game_force_begun`,
`game_ended`, `player_confirmed`, `player_declined`, `player_deferred`,
`player_timed_out`, `player_filled`, `player_left`, `settings_updated`.

### Confirmation

| Method | Path               | Description                                            |
| ------ | ------------------ | ------------------------------------------------------ |
| `POST` | `/api/confirm`     | Submit a yes/no/defer response (from app button).      |
| `POST` | `/api/sms/webhook` | Twilio inbound SMS webhook (from player text message). |

**Confirm request body:**

```json
{
  "player_id": 1,
  "game_id": 1,
  "response": "yes"
}
```

**SMS webhook:** Receives Twilio's standard `application/x-www-form-urlencoded`
POST. Parses `From` (phone number) and `Body` (yes/no/defer). Returns TwiML
`<Message>` response.

### Real-time Events

> **Note:** The SSE endpoint exists in the backend but is **not used** by the
> web frontend. PythonAnywhere's WSGI adapter (a2wsgi) would block a worker
> thread for every open SSE connection. The web app uses 5-second polling
> instead.

| Method | Path          | Description                                                          |
| ------ | ------------- | -------------------------------------------------------------------- |
| `GET`  | `/api/events` | Server-Sent Events stream (available but unused by current clients). |

Events are plain strings wrapped in the SSE `data:` format:

- `data: connected` — on initial connect
- `data: {"type": "game_update"}` — game state changed
- `data: {"type": "queue_update"}` — waiting list changed
- `: keepalive` — 30-second heartbeat to prevent proxy timeouts

---

## 7. Notification System

### 7.1 Channels

A player is notified via two channels simultaneously:

1. **SMS** — A text message containing the game number, confirmation deadline,
   and a link to the app. Sent via Twilio. Configurable with `STUB_SMS=true` for
   development (messages are logged instead of sent).

2. **Push notification** — A push alert sent to the player's registered Expo
   token. Sent via the Expo Push HTTP v2 API. Configurable with `STUB_PUSH=true`
   for development. The notification payload includes `game_id` and `player_id`
   in the `data` field so the mobile app can display the confirmation modal
   immediately on tap.

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

Confirmation timeouts are managed with `threading.Timer` (not asyncio). This is
required for compatibility with PythonAnywhere's WSGI/uWSGI environment, where
asyncio tasks do not survive the uWSGI fork process.

- When a slot is created, `_schedule_timeout(player_id, game_id)` is called.
- A `threading.Timer(CONFIRM_TIMEOUT_SECONDS, _timeout_job)` is started. The
  timer is daemon-mode so it doesn't prevent server shutdown.
- `_timeout_job` opens a new DB session, calls `handle_timeout()`, commits, then
  closes the session.
- Timers are stored in `_timeout_tasks: dict[(player_id, game_id), Timer]`.
- When a player responds (any answer), `_cancel_timeout(player_id, game_id)`
  calls `timer.cancel()`.
- `reset_all()` cancels all pending timers and clears `_timeout_tasks`.

**Limitation:** In-process timers do not survive a server restart. If the server
restarts while a game is in confirmation, the 5-minute clocks reset. For
production, these could be replaced with a persistent task queue (e.g., ARQ +
Redis).

---

## 8. Frontend Design

### 8.1 Web Application

Built with React 18, Vite, and Tailwind CSS. Single-page application served on
port 5173 in development, with a Vite proxy forwarding `/api` requests to the
backend on port 8000.

#### Page Layout

```
┌────────────────────────────────────┐
│  🏐 Volleyball Scheduler [12:34:05] Alice S. │  ← Header (sticky); digital clock (dark bg,
│                                              │    green digits, 24 h) always visible
├────────────────────────────────────┤
│                                    │
│  ┌─────────────────────────────┐   │
│  │  🏐 You're up for Game #3!  │   │  ← Confirmation banner (visible
│  │  [Yes] [No] [Defer]  4:32   │   │     only when player has a
│  └─────────────────────────────┘   │     pending slot); MM:SS countdown
│                                    │     turns red/pulses under 60 s
│  [ Live ] [ Past Games ]           │  ← Tab nav
│                                    │
│  ┌─────────────────────────────┐   │
│  │  Current Game #3            │   │
│  │  On Court (12/12)           │   │  ← CourtView
│  │  Alice S.  Bob J.  …        │   │
│  │  Awaiting Confirmation (2)  │   │
│  │  Carol D. 🕐 4:32           │   │  ← clock + MM:SS per pending slot,
│  │  Dave M.  🕐 3:51           │   │     red/pulsing under 60 s
│  └─────────────────────────────┘   │
│                                    │
│  ┌─────────────────────────────┐   │
│  │  Waiting List (4)           │   │
│  │  1. Carol D.  [Defer][Leave] │   │  ← WaitingListView
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

Player identity is stored in `localStorage` (via `usePlayer` hook) and persists
across page reloads. No authentication is implemented; the app operates on a
trusted local network model.

Live game state is fetched via the `useGameState` hook, which polls
`/api/games/current` and `/api/queue` every 5 seconds. SSE was removed because
PythonAnywhere's WSGI adapter would block one worker per open connection.

**Timestamp rendering.** The backend stores all timestamps as UTC via
`datetime.utcnow()` without a timezone suffix. Clients append `"Z"` before
passing to `new Date()` so the browser treats them as UTC; `toLocaleString()`
then converts to the viewer's local timezone. This applies to past game
start/end times in `PastGamesView`.

### 8.2 Mobile Application

Built with React Native and Expo, using Expo Router for file-based navigation.
Shares the same API surface as the web app.

#### Screens

| Screen   | File               | Description                                     |
| -------- | ------------------ | ----------------------------------------------- |
| Home     | `app/index.tsx`    | Court view, queue, controls, confirmation modal |
| Register | `app/register.tsx` | One-time player registration form               |
| History  | `app/history.tsx`  | Past games list                                 |

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

| Concern            | Web                   | Mobile                   |
| ------------------ | --------------------- | ------------------------ |
| Player persistence | `localStorage`        | `AsyncStorage`           |
| Live updates       | 5s polling            | 5s polling               |
| Confirmation       | Banner in page        | Bottom-sheet modal       |
| Leave queue        | Inline "Leave" button | Destructive alert dialog |

---

## 9. Real-time Updates

### Current Architecture (Polling)

The web client polls every 5 seconds:

```
Browser
  every 5 s ──► GET /api/games/current
  every 5 s ──► GET /api/queue
```

SSE (`GET /api/events`) is implemented in the backend and the `broadcast_update`
helper still fires on state changes, but **no web client subscribes to it**
because PythonAnywhere's WSGI adapter would block a worker thread per open
connection indefinitely.

### SSE Backend (Available, Unused by Web)

The SSE infrastructure remains in `app/api/events.py` and
`scheduler.broadcast_update()`. It can be re-enabled for clients that run
against a proper ASGI server (uvicorn direct, not behind a2wsgi):

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

All configuration is read from environment variables (or a `.env` file) via
Pydantic `BaseSettings`.

**Backend (`.env`):**

| Variable                  | Default                     | Description                                                 |
| ------------------------- | --------------------------- | ----------------------------------------------------------- |
| `DATABASE_URL`            | `sqlite:///./volleyball.db` | SQLAlchemy database connection string                       |
| `MAX_PLAYERS`             | `12`                        | Maximum players per game                                    |
| `CONFIRM_TIMEOUT_SECONDS` | `300`                       | Confirmation window in seconds (5 minutes)                  |
| `OPERATOR_SECRET`         | `change-me-in-production`   | Secret key for operator-only endpoints                      |
| `ALLOWED_ORIGINS`         | `http://localhost:5173,...` | Comma-separated CORS allowed origins                        |
| `STUB_SMS`                | `true`                      | If true, log SMS messages instead of sending via Twilio     |
| `STUB_PUSH`               | `true`                      | If true, log push notifications instead of sending via Expo |
| `STUB_EMAIL`              | `true`                      | If true, skip email sending (auto-verify makes this safe)   |
| `TWILIO_ACCOUNT_SID`      | _(empty)_                   | Twilio account SID (required when `STUB_SMS=false`)         |
| `TWILIO_AUTH_TOKEN`       | _(empty)_                   | Twilio auth token                                           |
| `TWILIO_FROM_NUMBER`      | _(empty)_                   | Twilio sender phone number (E.164 format)                   |
| `RESEND_API_KEY`          | _(empty)_                   | Resend API key (required when `STUB_EMAIL=false`)           |
| `EMAIL_FROM`              | _(empty)_                   | Sender email address for Resend                             |
| `BASE_URL`                | `http://localhost:8000`     | Public-facing URL embedded in SMS messages                  |

**Web frontend (`.env` / Vercel env vars):**

| Variable               | Default                   | Description                                                |
| ---------------------- | ------------------------- | ---------------------------------------------------------- |
| `VITE_API_URL`         | _(empty — same origin)_   | Backend base URL (set to PythonAnywhere URL in production) |
| `VITE_OPERATOR_SECRET` | `change-me-in-production` | Operator secret for the web operator controls              |

**Mobile frontend:**

| Variable              | Default                 | Description                             |
| --------------------- | ----------------------- | --------------------------------------- |
| `EXPO_PUBLIC_API_URL` | `http://localhost:8000` | Backend base URL used by the mobile app |

---

## 11. Testing Strategy

### 11.1 Test Scope

The test suite (`backend/tests/test_scenarios.py`) contains **91 unit tests**
that cover every rule in the specification. Tests run against an in-memory
SQLite database with no network calls (notification services are stubbed) and
timeouts triggered manually.

### 11.2 Test Structure

Each test class maps to one specification rule:

| Class                                      | Requirement                                                                     | Tests |
| ------------------------------------------ | ------------------------------------------------------------------------------- | ----- |
| `TestScenario1_MaxTwelvePlayers`           | R1 — max 12 players                                                             | 2     |
| `TestScenario2_SignupNumbers`              | R2 — first-come-first-served numbers                                            | 3     |
| `TestScenario3_MoreThan12Players`          | R3 — first 12 play, rest wait                                                   | 3     |
| `TestScenario4_NewArrivalsJoinWaitingList` | R4 — late arrivals join queue                                                   | 2     |
| `TestScenario5_GameRotation`               | R5 — court rotation after game                                                  | 3     |
| `TestScenario6_AtMost12Players`            | R6 — everyone plays if ≤12                                                      | 6     |
| `TestScenario7_LeaveWaitingList`           | R7 — leave queue at any time                                                    | 5     |
| `TestScenario8_ConfigurableTimeout`        | R8 — 5-min configurable timeout                                                 | 5     |
| `TestScenario9_ConfirmYes`                 | R9 — yes marks as playing                                                       | 3     |
| `TestScenario10_ConfirmNo`                 | R10 — no → end of queue                                                         | 5     |
| `TestScenario11_ConfirmDefer`              | R11 — defer swaps player to position of first eligible; preserves signup number | 6     |
| `TestScenario12_ValidResponses`            | R12 — case-insensitive responses                                                | 11    |
| `TestScenario13_DisplayNames`              | R13 — display name format (`FirstName L`, brackets)                             | 5     |
| `TestScenario14_SignupNumbersVisible`      | R14 — signup numbers shown                                                      | 3     |
| `TestScenario15_LeaveGameMidPlay`          | R7a — leave active game, removed from queue                                     | 5     |
| `TestScenario16_ResetAll`                  | R7b — Start Over preserves history                                              | 5     |
| `TestScenario17_Deregister`                | Registration spec — deregister rules                                            | 4     |
| `TestScenario18_ClearHistory`              | Clear History resets game ID sequence                                           | 4     |
| `TestScenario19_QueueDefer`                | R7 — waiting list defer (swap with next)                                        | 4     |
| `TestEdgeCases`                            | Edge cases                                                                      | 5     |

### 11.3 Running Tests

```bash
cd backend
source .venv/bin/activate
pytest tests/test_scenarios.py -v
```

### 11.4 Key Test Design Decisions

**In-memory database per test.** Each test receives a fresh SQLite in-memory
database via the `db` fixture. This gives perfect isolation without file I/O
overhead.

**Manual timeout triggering.** Since tests should not fire real
`threading.Timer` callbacks, the `db` fixture calls
`scheduler._timeout_tasks.clear()` before each test. Tests that verify timeout
behaviour call `scheduler.handle_timeout()` directly, bypassing the timer
entirely.

**Chain-of-declines edge case.** When all backup players decline, the game
starts with only the confirmed players. The test verifies this by triggering a
third decline when only one backup player exists, causing the queue to be
exhausted and the game to start with one confirmed player.

**All-timeout batch fill.** When every notified player times out (confirmed = 0)
but the queue has remaining players, `_try_fill_open_slots` must still run. The
`confirmed == 0` early-return guard was removed to ensure queue players always
get their chance to confirm — the game only remains in OPEN state (never starts)
if both confirmed = 0 and the queue is empty.

**Deferred player eligible for batch fill.** `_try_fill_open_slots` calls
`fill_slot(allow_requeue=True)` so that a player who deferred (DECLINED slot,
re-inserted into queue) is not permanently blocked when the queue would
otherwise be too small. During the live confirmation phase `fill_slot` is called
with the default `allow_requeue=False`, preventing immediate re-draw of a player
who just deferred.

---

## 12. Deployment

### 12.1 Backend (PythonAnywhere)

The production backend runs on **PythonAnywhere free tier** (WSGI only, no
long-running async).

Key files:

- `backend/wsgi.py` — PythonAnywhere WSGI entry. Uses a lazy singleton pattern
  to initialise `a2wsgi.ASGIMiddleware` inside the first request, after uWSGI
  has forked worker processes. This avoids the
  background-thread-doesn't-survive-fork hang.
- `backend/app/main.py` — Calls `init_db()` at module import time (not in an
  asyncio lifespan hook).

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

After code changes: `git pull` in the backend directory, then reload the web app
via the PythonAnywhere Web tab.

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

- `VITE_API_URL` — PythonAnywhere backend URL (e.g.
  `https://allisonzai.pythonanywhere.com`)
- `VITE_OPERATOR_SECRET` — operator secret (must match backend
  `OPERATOR_SECRET`)

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

Live game updates on mobile use 5-second polling. If lower latency is needed,
add SSE support via `react-native-sse` or WebSockets.

### 12.4 SMS (Twilio)

1. Create a Twilio account and purchase a phone number.
2. Set `STUB_SMS=false` and fill in the Twilio credentials in `.env`.
3. Configure the Twilio number's inbound webhook URL to
   `https://<BASE_URL>/api/sms/webhook`.
4. Ensure `BASE_URL` in `.env` matches the public hostname so reply links in SMS
   messages resolve correctly.

### 12.5 Push Notifications (Expo)

Push notifications work automatically via the Expo Push API when
`STUB_PUSH=false`. No server-side credentials are required for the Expo service.
For Firebase Cloud Messaging (Android) or APNs (iOS) direct delivery, configure
the keys in the Expo EAS dashboard and rebuild the app.
