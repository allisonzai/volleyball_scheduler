# Volleyball Scheduler — Specification

> Single source of truth for product requirements.
> Original document: https://bit.ly/3PSKZTa
> When adding new requirements, update this file and restart from it.

## Game Rules

1. Every game can only have up to 12 players.
2. To play, every player must sign up to receive a number assigned on a
   first-come, first-served basis.
3. If the number of players is more than 12, we can start the game with the
   first 12 players and leave the other players waiting for the next game.
4. While the game is ongoing the newly arriving players will add to the waiting
   list.
5. Once a game is completed the players on the court will be added to the
   waiting list and the first 12 players will play the next game.
6. If the number of the players is less than or equal to 12, we don't need to
   schedule the game because everyone can play.
7. Any player is allowed to leave while they are in the waiting list.
7a. A confirmed player may leave an active game at any time. They are moved to
    the end of the waiting list and the next queued player is notified.
7b. The operator may use "Start Over" to cancel the current game and clear the
    waiting list at any time. Player accounts are preserved.
8. A player currently playing (pending confirmation or confirmed in an active
   game) is not allowed to join the waiting list.
9. The player scheduled for a game will be notified and wait for up to
   5 minutes (configurable).
10. If they confirm **yes**, they are marked as playing.
11. If they confirm **no**, they will be taken out of the current game and put
    at the end of the waiting list and the next person is notified.
12. If they confirm **defer**, they are put at the start of the waiting list and
    the next person is notified.
13. Confirmation is done by typing `yes`, `no`, or `defer` in a short message,
    or by clicking the corresponding button in the app.

## Player Registration

A player must provide:

- First name and last name
- Mobile phone number (for SMS)
- Email address
- Password (minimum 6 characters)

Players can register and deregister via the web interface. Deregistration is
blocked while the player is in an active game.

### Account Verification

Players are automatically verified upon registration — no email code or SMS
code is required. A player may join the waiting list immediately after signing
up.

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
- If two players share the same display name, disambiguate by appending the
  last four digits of their phone number — e.g. `Alice J [4242]`

## Notifications

A player can be notified via:

- SMS to their phone number (via Twilio)
- Push notification to their phone app (via Expo)

## Operator Controls

Operators authenticate using the `X-Operator-Secret` header. The following
actions are available:

- **Start New Game**: creates a new game and populates it with up to 12 players
  from the front of the waiting list. Each selected player is notified and
  enters the confirmation flow.
- **End Game**: marks the current game as finished. Players who were confirmed
  in the game are appended to the end of the waiting list, and the next game is
  automatically populated from the queue.
- **Start Over**: cancels the active game and clears the entire waiting list.
  Player accounts are preserved; no players are deleted.

## User Interface

Two interfaces are required:

1. **Web page** — players can register, sign in, deregister, see who is
   playing, who is waiting, and browse past games.
2. **Phone app** — Android and iOS; mirrors the web page and supports in-app
   confirmation buttons.

For the current game and waiting list, show every player's display name and
their signup number (assigned when they first joined the queue).
