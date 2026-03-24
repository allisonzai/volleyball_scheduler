#!/usr/bin/env python3
"""
Seed script — registers fake players and runs test scenarios.

Usage:
  # Register 15 players and join them all to the queue (default)
  python scripts/seed.py

  # Full demo: register → queue → start game → everyone confirms yes → end game
  python scripts/seed.py --demo

  # Scenario: some players leave the queue / leave mid-game and go home
  python scripts/seed.py --scenario players-leave

  # Scenario: a game is running and a few new players arrive late
  python scripts/seed.py --scenario late-arrivals

  # Clean up: deregister all seeded players (reads seed_state.json)
  python scripts/seed.py --cleanup

  # Point at a different backend
  python scripts/seed.py --url https://allisonzai.pythonanywhere.com
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import httpx
from dotenv import dotenv_values

# Load backend/.env so BASE_URL and OPERATOR_SECRET are available by default
_env = dotenv_values(Path(__file__).parent.parent / ".env")

# ---------------------------------------------------------------------------
# Fake player data
# ---------------------------------------------------------------------------

PLAYERS = [
    ("Alice",   "Smith",    "+12125550101", "alice.smith@example.com"),
    ("Bob",     "Jones",    "+12125550102", "bob.jones@example.com"),
    ("Carol",   "Davis",    "+12125550103", "carol.davis@example.com"),
    ("Dave",    "Martinez", "+12125550104", "dave.martinez@example.com"),
    ("Eve",     "Wilson",   "+12125550105", "eve.wilson@example.com"),
    ("Frank",   "Taylor",   "+12125550106", "frank.taylor@example.com"),
    ("Grace",   "Anderson", "+12125550107", "grace.anderson@example.com"),
    ("Hank",    "Thomas",   "+12125550108", "hank.thomas@example.com"),
    ("Ivy",     "Jackson",  "+12125550109", "ivy.jackson@example.com"),
    ("Jack",    "White",    "+12125550110", "jack.white@example.com"),
    ("Karen",   "Harris",   "+12125550111", "karen.harris@example.com"),
    ("Leo",     "Martin",   "+12125550112", "leo.martin@example.com"),
    ("Mia",     "Garcia",   "+12125550113", "mia.garcia@example.com"),
    ("Nate",    "Lopez",    "+12125550114", "nate.lopez@example.com"),
    ("Olivia",  "Lee",      "+12125550115", "olivia.lee@example.com"),
    ("Pete",    "Walker",   "+12125550116", "pete.walker@example.com"),
    ("Quinn",   "Hall",     "+12125550117", "quinn.hall@example.com"),
    ("Rosa",    "Allen",    "+12125550118", "rosa.allen@example.com"),
    ("Sam",     "Young",    "+12125550119", "sam.young@example.com"),
    ("Tina",    "King",     "+12125550120", "tina.king@example.com"),
]

DEFAULT_PASSWORD = "test1234"
STATE_FILE = Path(__file__).parent / "seed_state.json"


# ---------------------------------------------------------------------------
# Print helpers
# ---------------------------------------------------------------------------

def ok(msg: str) -> None:
    print(f"  \033[32m✓\033[0m  {msg}")

def err(msg: str) -> None:
    print(f"  \033[31m✗\033[0m  {msg}", file=sys.stderr)

def info(msg: str) -> None:
    print(f"  \033[34m→\033[0m  {msg}")

def section(title: str) -> None:
    print(f"\n\033[1m── {title} ──\033[0m")


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def register(client: httpx.Client, first: str, last: str, phone: str, email: str) -> dict | None:
    r = client.post("/players", json={
        "first_name": first, "last_name": last,
        "phone": phone, "email": email,
        "password": DEFAULT_PASSWORD,
    })
    if r.status_code == 201:
        data = r.json()
        ok(f"Registered {data['display_name']}  (id={data['id']})")
        return data
    elif r.status_code == 400 and "already registered" in r.text:
        r2 = client.post("/players/signin", json={"phone": phone, "password": DEFAULT_PASSWORD})
        if r2.status_code == 200:
            data = r2.json()
            info(f"Already exists: {data['display_name']}  (id={data['id']}) — signed in")
            return data
        err(f"Exists but sign-in failed for {first} {last}: {r2.text}")
        return None
    err(f"Failed to register {first} {last}: {r.status_code} {r.text}")
    return None


def join_queue(client: httpx.Client, player: dict) -> bool:
    r = client.post(
        "/queue/join",
        json={"player_id": player["id"]},
        headers={"X-Player-Token": player["secret_token"]},
    )
    if r.status_code in (200, 201):
        ok(f"{player['display_name']} joined the queue")
        return True
    elif r.status_code == 400:
        info(f"{player['display_name']} already in queue (skipped)")
        return True
    err(f"Could not join queue for {player['display_name']}: {r.status_code} {r.text}")
    return False


def leave_queue(client: httpx.Client, player: dict) -> bool:
    r = client.delete(
        f"/queue/{player['id']}",
        headers={"X-Player-Token": player["secret_token"]},
    )
    if r.status_code == 200:
        ok(f"{player['display_name']} left the queue  (going home)")
        return True
    err(f"Could not leave queue for {player['display_name']}: {r.status_code} {r.text}")
    return False


def leave_game(client: httpx.Client, player: dict, game_id: int) -> bool:
    r = client.post(
        f"/games/{game_id}/leave",
        headers={"X-Player-Token": player["secret_token"]},
    )
    if r.status_code == 204:
        ok(f"{player['display_name']} left the game mid-play  (going home)")
        return True
    err(f"Could not leave game for {player['display_name']}: {r.status_code} {r.text}")
    return False


def start_game(client: httpx.Client, operator_secret: str) -> dict | None:
    r = client.post("/games/start", headers={"X-Operator-Secret": operator_secret})
    if r.status_code == 201:
        game = r.json()
        ok(f"Started Game #{game['id']}  (status={game['status']})")
        return game
    err(f"Could not start game: {r.status_code} {r.text}")
    return None


def end_game(client: httpx.Client, game_id: int, operator_secret: str) -> None:
    r = client.post(f"/games/{game_id}/end", headers={"X-Operator-Secret": operator_secret})
    if r.status_code == 200:
        ok(f"Ended Game #{game_id}")
    else:
        err(f"Could not end game: {r.status_code} {r.text}")


def fetch_game(client: httpx.Client, game_id: int) -> dict | None:
    r = client.get(f"/games/{game_id}")
    return r.json() if r.status_code == 200 else None


def confirm_pending(client: httpx.Client, game: dict, players_by_id: dict, response: str = "yes") -> None:
    for slot in game["slots"]:
        if slot["status"] == "pending_confirmation":
            p = players_by_id.get(slot["player_id"])
            if not p:
                continue
            r = client.post(
                "/confirm",
                json={"player_id": p["id"], "game_id": game["id"], "response": response},
                headers={"X-Player-Token": p["secret_token"]},
            )
            if r.status_code == 200:
                ok(f"{p['display_name']} confirmed '{response}'")
            else:
                err(f"Confirm failed for {p['display_name']}: {r.status_code} {r.text}")
            time.sleep(0.05)


def deregister(client: httpx.Client, player: dict) -> None:
    r = client.delete(
        f"/players/{player['id']}",
        headers={"X-Player-Token": player["secret_token"]},
    )
    if r.status_code == 204:
        ok(f"Deregistered {player['display_name']}")
    else:
        err(f"Could not deregister {player['display_name']}: {r.status_code} {r.text}")


def print_state(client: httpx.Client) -> None:
    """Print a summary of the current queue and active game."""
    print()
    r = client.get("/games/current")
    game = r.json() if r.status_code == 200 else None
    if game:
        confirmed = [s for s in game["slots"] if s["status"] == "confirmed"]
        pending   = [s for s in game["slots"] if s["status"] == "pending_confirmation"]
        print(f"  Game #{game['id']} [{game['status']}]")
        if confirmed:
            print(f"    On court  : {', '.join(s['display_name'] for s in confirmed)}")
        if pending:
            print(f"    Pending   : {', '.join(s['display_name'] for s in pending)}")
    else:
        print("  No active game.")

    r2 = client.get("/queue")
    queue = r2.json() if r2.status_code == 200 else []
    if queue:
        print(f"  Waiting list ({len(queue)}): {', '.join(e['display_name'] for e in queue)}")
    else:
        print("  Waiting list: empty")
    print()


def bulk_register(client: httpx.Client, entries: list[tuple]) -> list[dict]:
    """Register a batch of players from PLAYERS-style tuples."""
    out = []
    for first, last, phone, email in entries:
        p = register(client, first, last, phone, email)
        if p:
            out.append(p)
    return out


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_seed(client: httpx.Client, count: int, join: bool) -> None:
    section(f"Registering {count} players")
    registered = bulk_register(client, PLAYERS[:count])

    if join and registered:
        section(f"Joining {len(registered)} players to queue")
        for p in registered:
            join_queue(client, p)

    STATE_FILE.write_text(json.dumps(registered, indent=2))
    print(f"\n  Saved state → {STATE_FILE}")
    print(f"\n  Done. {len(registered)} players registered", "and queued." if join else "(not queued).")


def cmd_demo(client: httpx.Client, operator_secret: str) -> None:
    """Full flow: 15 players → queue → start → confirm all → end."""
    section("Demo: full game flow")

    print("\n[1/4] Registering 15 players and joining queue")
    registered = []
    for first, last, phone, email in PLAYERS[:15]:
        p = register(client, first, last, phone, email)
        if p:
            registered.append(p)
            join_queue(client, p)

    players_by_id = {p["id"]: p for p in registered}
    STATE_FILE.write_text(json.dumps(registered, indent=2))

    print("\n[2/4] Starting game")
    game = start_game(client, operator_secret)
    if not game:
        return

    print("\n[3/4] Confirming all pending slots")
    game = fetch_game(client, game["id"]) or game
    confirm_pending(client, game, players_by_id, "yes")

    print("\n[4/4] Ending game")
    end_game(client, game["id"], operator_secret)

    print_state(client)
    print(f"  Demo complete. {len(registered)} players seeded, 1 game played.")


def cmd_scenario_players_leave(client: httpx.Client, operator_secret: str) -> None:
    """
    Scenario: players leave for home.

    Setup:  18 players sign up and join the queue.
    Step 1: Start a game — first 12 are asked to confirm.
    Step 2: 3 players in the waiting list decide to leave before being called.
    Step 3: 9 players confirm yes.  3 remaining pending slots pull from the queue.
    Step 4: Game is now in progress.  2 confirmed players leave mid-game (go home).
            The next 2 in the queue are notified to fill their spots.
    Result: Active game with 10 original + 2 replacement players;
            remaining queue shows the late-leavers at the end.
    """
    section("Scenario: Players Leave For Home")

    print("\n[1/4] Register 18 players and join queue")
    registered = bulk_register(client, PLAYERS[:18])
    for p in registered:
        join_queue(client, p)

    players_by_id = {p["id"]: p for p in registered}
    STATE_FILE.write_text(json.dumps(registered, indent=2))

    print("\n[2/4] Start game")
    game = start_game(client, operator_secret)
    if not game:
        return
    game = fetch_game(client, game["id"]) or game

    # Players 13–18 are in the queue (positions 1–6 of the waiting list after
    # the first 12 were pulled out for the game).
    queue_r = client.get("/queue")
    queue = queue_r.json() if queue_r.status_code == 200 else []

    print("\n[3/4] Three waiting players decide to leave before being called")
    leavers_queue = [p for p in registered if any(e["player_id"] == p["id"] for e in queue)][:3]
    for p in leavers_queue:
        leave_queue(client, p)

    print("\n[4/4] Remaining pending players confirm — game fills up")
    game = fetch_game(client, game["id"]) or game
    confirm_pending(client, game, players_by_id, "yes")

    # Now two confirmed court players decide to leave mid-game
    game = fetch_game(client, game["id"]) or game
    confirmed_slots = [s for s in game["slots"] if s["status"] == "confirmed"]
    leavers_game = [players_by_id[s["player_id"]] for s in confirmed_slots[:2]
                    if s["player_id"] in players_by_id]

    print(f"\n[bonus] Two court players go home mid-game")
    for p in leavers_game:
        leave_game(client, p, game["id"])

    print_state(client)
    info("3 players left the queue before being called.")
    info("2 confirmed players left mid-game; replacements pulled from the waiting list.")


def cmd_scenario_late_arrivals(client: httpx.Client, operator_secret: str) -> None:
    """
    Scenario: new players arrive after the game has already started.

    Setup:  12 players sign up and join the queue — exactly a full game.
    Step 1: Start the game — all 12 are confirmed immediately (≤12 path).
    Step 2: 4 new players show up and join the waiting list while the game runs.
    Step 3: 2 more players arrive after that.
    Result: Active game with 12 on court; 6 newcomers queued in arrival order,
            ready for the next game.
    """
    section("Scenario: Late Arrivals")

    print("\n[1/3] Register 12 early birds and join queue")
    early = bulk_register(client, PLAYERS[:12])
    for p in early:
        join_queue(client, p)

    STATE_FILE.write_text(json.dumps(early, indent=2))

    print("\n[2/3] Start game (all 12 confirmed immediately)")
    game = start_game(client, operator_secret)
    if not game:
        return

    print("\n[3/3] Late arrivals join while game is in progress")

    print("\n  First wave — 4 players arrive:")
    late_wave1 = bulk_register(client, PLAYERS[12:16])
    for p in late_wave1:
        join_queue(client, p)

    time.sleep(0.3)  # small pause to make arrival order visible in the UI

    print("\n  Second wave — 2 more players arrive:")
    late_wave2 = bulk_register(client, PLAYERS[16:18])
    for p in late_wave2:
        join_queue(client, p)

    all_players = early + late_wave1 + late_wave2
    STATE_FILE.write_text(json.dumps(all_players, indent=2))

    print_state(client)
    info("12 players on court.  6 late arrivals in the queue, in arrival order.")
    info("Operator can end the game and press 'Start New Game' to rotate.")


def cmd_cleanup(client: httpx.Client) -> None:
    if not STATE_FILE.exists():
        err("No seed_state.json found — nothing to clean up.")
        return
    players = json.loads(STATE_FILE.read_text())
    section(f"Deregistering {len(players)} seeded players")
    for p in players:
        deregister(client, p)
    STATE_FILE.unlink()
    print("\n  Cleanup complete.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Seed fake players into the Volleyball Scheduler.")
    parser.add_argument(
        "--url",
        default=_env.get("BASE_URL", "http://localhost:8000"),
        help="Backend base URL (default: BASE_URL from backend/.env)",
    )
    parser.add_argument("--count", type=int, default=15, help="Number of players to register (max 20)")
    parser.add_argument("--no-queue", action="store_true", help="Register players but don't join queue")
    parser.add_argument("--demo", action="store_true", help="Full flow demo")
    parser.add_argument(
        "--scenario",
        choices=["players-leave", "late-arrivals"],
        help="Run a named test scenario",
    )
    parser.add_argument("--cleanup", action="store_true", help="Deregister all seeded players")
    parser.add_argument(
        "--operator-secret",
        default=_env.get("OPERATOR_SECRET", os.environ.get("OPERATOR_SECRET", "change-me-in-production")),
        help="Operator secret (default: OPERATOR_SECRET from backend/.env)",
    )
    args = parser.parse_args()

    args.count = min(args.count, len(PLAYERS))
    base = args.url.rstrip("/") + "/api"
    print(f"\nTarget: {base}")

    with httpx.Client(base_url=base, timeout=15, trust_env=False) as client:
        if args.cleanup:
            cmd_cleanup(client)
        elif args.demo:
            cmd_demo(client, args.operator_secret)
        elif args.scenario == "players-leave":
            cmd_scenario_players_leave(client, args.operator_secret)
        elif args.scenario == "late-arrivals":
            cmd_scenario_late_arrivals(client, args.operator_secret)
        else:
            cmd_seed(client, args.count, join=not args.no_queue)


if __name__ == "__main__":
    main()
