# Volleyball Scheduler — Specification

> Single source of truth for product requirements. Original document:
> https://bit.ly/3PSKZTa When adding new requirements, update this file and
> restart from it.

## Game Rules

1.  Every game can only have up to 12 players.
2.  To play, every player must sign up to receive a number assigned on a
    first-come, first-served basis.
3.  If the number of players is more than 12, we can start the game with the
    first 12 players and leave the other players waiting for the next game.
4.  While the game is ongoing the newly arriving players will add to the waiting
    list.
5.  Once a game is completed the players on the court will be added to the
    waiting list and the first 12 players will play the next game.
6.  If the number of the players is less than or equal to 12, everyone can play
    — but confirmation is still required from each player before the game
    starts.
7.  Any player is allowed to leave while they are in the waiting list. 7a. A
    confirmed player may leave an active game at any time. They are removed from
    both the game and the waiting list entirely. The next queued player is
    notified to fill the vacated spot. 7b. The operator may use "Start Over" to
    cancel the current game and clear the waiting list at any time. Player
    accounts are preserved.
8.  A player currently playing (pending confirmation or confirmed in an active
    game) is not allowed to join the waiting list.
9.  The player scheduled for a game will be notified and wait for up to 5
    minutes (configurable).
10. If they confirm **yes**, they are marked as playing.
11. If they confirm **no** (or do not respond within the timeout), they will be
    taken out of the current game and not be added to the waiting list. The
    first person in the waiting list who has not already deferred for the
    current game will be selected as a replacement immediately. If the queue
    (including deferred players who were re-inserted) is empty, the slot stays
    vacant until the operator clicks Begin Game or Start Over.
12. If they confirm **defer**, they will be taken out of the current game and
    swapped with the first person in the waiting list who has not already
    deferred for the current game. The deferred player is re-inserted into the
    queue and is eligible to be drawn again during a subsequent batch fill if
    the queue would otherwise be too small.
13. Confirmation is done by clicking the corresponding button in the app.
14. The player in the waiting list can choose **Leave** to remove them from the
    list or **Defer** to swap with the next person in the waiting list.

## Player Registration

A player must provide:

- First name and last name
- Mobile phone number (for SMS)
- Email address
- Password (minimum 6 characters)

Players can register and deregister via the web interface. Deregistration is
blocked while the player is in an active game.

### Account Verification

Players are automatically verified upon registration — no email code or SMS code
is required. A player may join the waiting list immediately after signing up.

> Note: Email infrastructure (Resend) is in place and can be used for
> verification flows or other notifications in the future.

### Sign In

A returning player signs in with their phone number and password.

### Security

- Each player is issued a secret token at registration used to authenticate
  state-mutating actions (join/leave queue, confirm game response, deregister).
- Game start and end operations require a separate operator secret key.
- CORS allowed origins are configurable and restricted in production.
- The SMS webhook validates the Twilio request signature in production.

## Display Names

- Format: `FirstName L` (first name + last-name initial)
- If two players share the same display name, disambiguate by appending the last
  four digits of their phone number — e.g. `Alice J [4242]`

## Notifications

A player can be notified via:

- SMS to their phone number (via Twilio)
- Push notification to their phone app (via Expo)

## Two-Phase Game Flow

A game goes through two explicit phases:

1. **Staging phase** (status: `open`) — operator clicks **Start Staging**.
   Players are notified and asked to confirm. Players who decline or defer
   are replaced automatically. A permanent game number is **not** yet
   assigned; cancelled staging sessions consume no number.

2. **Gaming phase** (status: `in_progress`) — operator clicks **Begin Game** to start a game and a game
   number is assigned when:
   - All player slots are confirmed, **or**
   - The queue is exhausted and at least one player has confirmed.

## Fill-Wait

When a replacement player is drawn from the queue while other slots are
still pending confirmation, the system computes the minimum remaining time
among the existing pending players, sets the new global confirmation timeout
to `min_remaining + FILL_WAIT_SECONDS`, and resets every pending player's
(including the replacement's) `notified_at` to now. All pending players
share the same fresh countdown from that moment.

## Operator Controls

Operators authenticate using the `X-Operator-Secret` header. The following
actions are available:

- **Start Staging**: creates a new game and populates it with up to 12
  players from the front of the waiting list. Each selected player is
  notified and enters the confirmation flow.
- **Begin Game #N**: force-transitions the staging game to IN_PROGRESS.
  Any still-pending slots are cancelled (those players are removed from
  the waiting list). Requires at least one confirmed player.
- **End Game #N**: marks the current game as finished. Confirmed players
  are appended to the end of the waiting list. The operator must press
  **Start Staging** to begin the next round.
- **Start Over**: cancels the active game and clears the entire waiting
  list. Player accounts are preserved; no players are deleted.
- **Save Settings**: updates confirm timeout and fill-wait seconds
  (both in minutes). Changes take effect immediately; in-flight pending
  timers are rescheduled to reflect the new timeout.

## Event Log

All significant game events are stored with timestamps in the `event_logs`
table and exposed via `GET /api/activity`. The web interface shows these in
the **Events** tab with a colour-coded timeline. Logged events include:

- Game staging started / game begun / game ended
- Player confirmed / declined / deferred / timed out
- Player called up from waiting list (fill)
- Player left mid-game
- Settings updated

## User Interface

Two interfaces are required:

1. **Web page** — players can register, sign in, deregister, see who is
   playing, who is waiting, browse past games, and view the event log.
2. **Phone app** — Android and iOS; mirrors the web page and supports
   in-app confirmation buttons.

For the current game and waiting list, show every player's display name
and their signup number (assigned when they first joined the queue).
