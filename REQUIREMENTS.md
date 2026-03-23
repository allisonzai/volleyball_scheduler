# Volleyball Scheduler — Requirements Document

> Comprehensive functional and non-functional requirements derived from the
> specification, design, and all implemented behaviour.
> For the authoritative one-page spec see `SPEC.md`.
> For architecture and data-model detail see `DESIGN.md`.

---

## 1. Purpose

Manage recreational volleyball game scheduling fairly and transparently.
Players sign up on a first-come-first-served basis, receive a confirmation
prompt before each game, and rotate through games automatically.

---

## 2. User Roles

| Role | Description |
|---|---|
| **Player** | Registers once; joins the waiting list; confirms or declines game invitations. |
| **Operator** | Controls game lifecycle (start, end, reset). Authenticated by a shared secret. |

---

## 3. Player Registration and Authentication

### 3.1 Registration

A player must provide:

- First name and last name
- Mobile phone number (E.164 format, unique)
- Email address (unique)
- Password (minimum 6 characters)

Players are **automatically verified** upon registration — no email or SMS
code is required. A player may join the waiting list immediately after
signing up.

### 3.2 Sign-in

A returning player signs in with their **phone number and password**.

### 3.3 Deregistration

A player may permanently delete their account via the web or mobile app.
Deregistration is **blocked** while the player has an active game slot
(pending confirmation or confirmed in an in-progress game).

### 3.4 Security Tokens

- Each player is issued a **secret token** at registration.
- The token must accompany all state-mutating player actions:
  join queue, leave queue, defer in queue, confirm game response,
  leave game mid-play, deregister.
- Token comparison must use a constant-time comparison to prevent
  timing attacks.

---

## 4. Display Names

- Format: `FirstName L` (first name + last-name initial).
- If two or more players share the same display name, each is
  disambiguated by appending the last four digits of their phone
  number in brackets — e.g. `Alice J [4242]`.
- Display names are recomputed whenever a new player registers whose
  name would create a collision.

---

## 5. Signup Numbers

- Each time a player **joins the waiting list** they are assigned a
  **signup number** — a session-scoped integer that increments
  monotonically (1, 2, 3, …).
- The counter **resets to 1** after a Start Over (the waiting list is
  cleared).
- A player's signup number **never changes** once assigned for a
  session — including when they defer in the queue or are re-inserted
  after deferring during game confirmation.
- The signup number is **copied onto the player's game slot** when
  they are moved from the queue into a game, so it remains available
  for display in the court view and past-games history even after the
  waiting-list row is deleted.
- Every player on the court and in the waiting list is shown alongside
  their signup number in the UI.

---

## 6. Waiting List

### 6.1 Joining

- Any registered player not currently in the waiting list and not
  currently in an active game (pending or confirmed) may join the
  waiting list.
- Players are appended to the end of the list in arrival order.

### 6.2 Leaving

- A player in the waiting list may leave at any time.
- Leaving removes the player from the list entirely.

### 6.3 Deferring (in-queue)

- A player in the waiting list may **Defer**, which swaps their
  position with the player immediately behind them.
- If the player is already last, the action is rejected (400).

### 6.4 Position Invariants

- Positions are compact integers `1 … N`, resequenced after every
  mutation (join, leave, defer, game start).
- A player may appear in the waiting list **at most once** at any time.

---

## 7. Game Lifecycle

### 7.1 Starting a Game

- The **operator** triggers game start.
- A game may only be started when there is no currently active game
  (status OPEN or IN_PROGRESS).
- Up to `MAX_PLAYERS` (default 12) players are taken from the front of
  the waiting list.
- **All selected players are notified and must confirm**, even when
  fewer than 12 players are present.
- Each selected player's signup number is saved on their game slot
  before they are removed from the waiting list.

### 7.2 Confirmation Flow

Once selected for a game, each player:

1. Receives an **SMS** and/or **push notification**.
2. Has a configurable window (default **5 minutes**) to respond.
3. Must respond with one of:

| Response | Effect |
|---|---|
| **Yes** | Player is marked as confirmed. |
| **No** | Player is removed from the game and from the waiting list entirely. |
| **Defer** | Player is removed from the game slot. The **first eligible queue player** (not already having a slot in this game) fills the vacated slot. The deferred player is re-inserted into the queue immediately before the next queue entry that has no slot in this game, preserving their original signup number. |
| *(no response / timeout)* | Treated identically to **No**. |

### 7.3 Batch Fill After All Pending Resolve

- Replacements are **not pulled one-by-one** as each player declines.
- The system waits until **all pending slots are resolved** (everyone
  has responded or timed out), then pulls all needed replacements
  from the queue at once.
- This applies even if `confirmed == 0` at that point — queue players
  deserve their chance. The game starts once at least one of the new
  batch confirms and the queue is exhausted.
- Each replacement player receives their own fresh notification and
  a full new confirmation window.
- If the queue is exhausted before all slots are filled:
  - If at least one player is confirmed → game transitions to
    IN_PROGRESS with however many confirmed.
  - If zero players confirmed → game remains OPEN until the operator
    clicks Start Over.

### 7.4 Game Start (IN_PROGRESS)

- The game transitions from OPEN to IN_PROGRESS when either:
  - All slots are confirmed (no pending remain, full complement), or
  - The queue is exhausted and at least one player is confirmed.

### 7.5 Leaving a Game Mid-Play

- A **confirmed** player may leave an active game (OPEN or IN_PROGRESS)
  at any time.
- They are removed from **both** the game slot and the waiting list
  entirely.
- The next eligible queue player is immediately notified to fill the
  vacated spot.

### 7.6 Ending a Game

- The **operator** ends the current game.
- All confirmed court players are appended to the **end** of the
  waiting list, in court seat order.
- Players whose slots were DECLINED, TIMED_OUT, or WITHDRAWN are not
  re-queued.
- The operator must press **Start New Game** to begin the next round;
  it does not start automatically.

### 7.7 Start Over (Reset)

- The operator may cancel the active game and **clear the entire
  waiting list** at any time.
- All pending confirmation timers are cancelled.
- Active game(s) are marked as FINISHED.
- **Player accounts and game history are preserved.**

---

## 8. Operator Controls

| Control | Condition | Effect |
|---|---|---|
| **Start New Game** | No active game | Creates game, notifies up to 12 players from queue |
| **End Game #N** | Active game exists | Marks game FINISHED; rotates confirmed players to end of queue |
| **Start Over** | Any time | Cancels active game, clears waiting list; history preserved |
| **Clear History** | Any time | Deletes all FINISHED game records and their slots |
| **Set Timeout** | Any time | Updates confirmation window (minimum 30 seconds) |

Operator actions require the `X-Operator-Secret` header matching the
configured `OPERATOR_SECRET`.

---

## 9. Notifications

Players are notified via two channels simultaneously when selected for a game:

- **SMS** — via Twilio; includes game number and confirmation deadline.
- **Push notification** — via Expo Push API; payload includes
  `game_id` and `player_id` so the mobile app can show the
  confirmation modal immediately on tap.

Both channels are stubbable via environment variables for development
and testing.

---

## 10. Confirmation Timeout

- Default: **5 minutes** (300 seconds).
- Configurable by the operator at runtime (minimum 30 seconds).
- Each player's countdown is anchored to `notified_at` (the timestamp
  recorded when their slot was created and notification sent).
- On expiry, the player is treated as having answered **No**:
  removed from the game and from the waiting list.
- Replacement players receive a **fresh, full** confirmation window
  starting from their own `notified_at`.

---

## 11. User Interface

### 11.1 Web Application

- Players can: register, sign in, sign out, deregister, join the
  waiting list, leave the waiting list, defer in the waiting list,
  confirm/decline/defer a game invitation, leave a game mid-play.
- All players can see: the current game (court and awaiting-confirmation
  sections with signup numbers), the full waiting list (with signup
  numbers), and past games.
- A **QR code** sharing the page URL is available in the header.
- A **countdown timer** (MM:SS) is shown on the confirmation banner,
  turning red and pulsing under 60 seconds.
- Operator controls are embedded on the same page (visible to anyone
  who knows the operator secret, which is baked into the build).

### 11.2 Mobile Application (iOS and Android)

- Mirrors the web page functionality.
- Supports in-app confirmation via a bottom-sheet modal triggered by
  push notification tap.
- Uses `AsyncStorage` for player identity persistence.

### 11.3 Live Updates

- Both clients poll `/api/games/current` and `/api/queue` every
  5 seconds.
- An SSE endpoint (`/api/events`) exists in the backend but is not
  used by current clients (incompatible with the WSGI hosting
  environment).

---

## 12. Past Games

- Finished games are listed in reverse chronological order.
- Each game shows: game number, start/end timestamps, and all players
  who were confirmed or withdrew (with signup number and a "left" label
  for withdrawn players).
- The operator may **Clear History** to delete all finished game
  records (resets the game ID sequence).

---

## 13. Security

| Concern | Requirement |
|---|---|
| Player actions | `X-Player-Token` header; verified with constant-time comparison |
| Operator actions | `X-Operator-Secret` header; verified with constant-time comparison |
| CORS | Allowed origins are configurable; must not use `*` in production |
| SMS webhook | Twilio request signature must be validated in production (`STUB_SMS=false`) |
| Passwords | Stored as PBKDF2-SHA256 hashes; minimum 6 characters |

---

## 14. Configuration

| Variable | Default | Description |
|---|---|---|
| `MAX_PLAYERS` | `12` | Maximum players per game |
| `CONFIRM_TIMEOUT_SECONDS` | `300` | Default confirmation window; mutable at runtime by operator |
| `OPERATOR_SECRET` | *(required)* | Protects game lifecycle endpoints |
| `DATABASE_URL` | `sqlite:///./volleyball.db` | SQLAlchemy connection string |
| `ALLOWED_ORIGINS` | `http://localhost:5173,…` | CORS allowed origins |
| `STUB_SMS` | `true` | Log SMS instead of sending |
| `STUB_PUSH` | `true` | Log push instead of sending |
| `STUB_EMAIL` | `true` | Skip email (auto-verify makes this safe) |
| `BASE_URL` | `http://localhost:8000` | Public URL embedded in SMS messages |
| `VITE_API_URL` | *(same origin)* | Backend URL for web frontend |
| `VITE_OPERATOR_SECRET` | *(required)* | Operator secret for web operator controls |

---

## 15. Non-Functional Requirements

| Requirement | Detail |
|---|---|
| **Hosting** | Backend: PythonAnywhere free tier (WSGI, no long-running async). Frontend: Vercel. |
| **Database** | SQLite (file-based); no migration framework — schema changes applied via `ALTER TABLE`. |
| **Confirmation timers** | Implemented with `threading.Timer` (daemon threads) for WSGI compatibility. Timers do not survive server restart. |
| **Scalability** | Single-server; designed for a small recreational group (tens of players). |
| **Test coverage** | 91 scenario-driven unit tests covering all specification rules; all must pass before merging changes to the scheduler or models. |
