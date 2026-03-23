#!/usr/bin/env python3
"""
Seed script — registers fake players and optionally runs through a full game flow.

Usage:
  # Register 15 players and join them all to the queue (default)
  python scripts/seed.py

  # Point at a different backend
  python scripts/seed.py --url https://allisonzai.pythonanywhere.com

  # Register players without joining the queue
  python scripts/seed.py --no-queue

  # Full demo: register → queue → start game → everyone confirms yes → end game
  python scripts/seed.py --demo

  # Clean up: deregister all seeded players (reads seed_state.json)
  python scripts/seed.py --cleanup
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import httpx

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
# Helpers
# ---------------------------------------------------------------------------

def ok(msg: str) -> None:
    print(f"  \033[32m✓\033[0m  {msg}")

def err(msg: str) -> None:
    print(f"  \033[31m✗\033[0m  {msg}", file=sys.stderr)

def info(msg: str) -> None:
    print(f"  \033[34m→\033[0m  {msg}")


def register(client: httpx.Client, first: str, last: str, phone: str, email: str) -> dict | None:
    try:
        r = client.post("/players", json={
            "first_name": first,
            "last_name": last,
            "phone": phone,
            "email": email,
            "password": DEFAULT_PASSWORD,
        })
        if r.status_code == 201:
            data = r.json()
            ok(f"Registered {data['display_name']}  (id={data['id']})")
            return data
        elif r.status_code == 400 and "already registered" in r.text:
            # Already exists — sign in to get the token
            r2 = client.post("/players/signin", json={"phone": phone, "password": DEFAULT_PASSWORD})
            if r2.status_code == 200:
                data = r2.json()
                info(f"Already exists: {data['display_name']}  (id={data['id']}) — signed in")
                return data
            else:
                err(f"Exists but sign-in failed for {first} {last}: {r2.text}")
                return None
        else:
            err(f"Failed to register {first} {last}: {r.status_code} {r.text}")
            return None
    except httpx.RequestError as e:
        err(f"Request error: {e}")
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
    else:
        err(f"Could not join queue for {player['display_name']}: {r.status_code} {r.text}")
        return False


def start_game(client: httpx.Client, operator_secret: str) -> dict | None:
    r = client.post("/games/start", headers={"X-Operator-Secret": operator_secret})
    if r.status_code == 201:
        game = r.json()
        ok(f"Started Game #{game['id']}  (status={game['status']})")
        return game
    else:
        err(f"Could not start game: {r.status_code} {r.text}")
        return None


def confirm_all(client: httpx.Client, game: dict, players_by_id: dict, response: str = "yes") -> None:
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
            time.sleep(0.05)  # small delay to avoid hammering


def end_game(client: httpx.Client, game_id: int, operator_secret: str) -> None:
    r = client.post(f"/games/{game_id}/end", headers={"X-Operator-Secret": operator_secret})
    if r.status_code == 200:
        ok(f"Ended Game #{game_id}")
    else:
        err(f"Could not end game: {r.status_code} {r.text}")


def deregister(client: httpx.Client, player: dict) -> None:
    r = client.delete(
        f"/players/{player['id']}",
        headers={"X-Player-Token": player["secret_token"]},
    )
    if r.status_code == 204:
        ok(f"Deregistered {player['display_name']}")
    else:
        err(f"Could not deregister {player['display_name']}: {r.status_code} {r.text}")


# ---------------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------------

def cmd_seed(client: httpx.Client, count: int, join: bool) -> None:
    print(f"\n── Registering {count} players ──")
    registered = []
    for first, last, phone, email in PLAYERS[:count]:
        p = register(client, first, last, phone, email)
        if p:
            registered.append(p)

    if join and registered:
        print(f"\n── Joining {len(registered)} players to queue ──")
        for p in registered:
            join_queue(client, p)

    STATE_FILE.write_text(json.dumps(registered, indent=2))
    print(f"\n  Saved state → {STATE_FILE}")
    print(f"\n  Done. {len(registered)} players registered", "and queued." if join else "(not queued).")


def cmd_demo(client: httpx.Client, operator_secret: str) -> None:
    """Full flow: seed 15 players → queue all → start game → confirm all → end game."""
    print("\n── Demo: full game flow ──")

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
    # Re-fetch game to get fresh slot list
    r = client.get(f"/games/{game['id']}")
    if r.status_code == 200:
        game = r.json()
    confirm_all(client, game, players_by_id, "yes")

    print("\n[4/4] Ending game")
    end_game(client, game["id"], operator_secret)

    print(f"\n  Demo complete. {len(registered)} players seeded, 1 game played.")


def cmd_cleanup(client: httpx.Client) -> None:
    if not STATE_FILE.exists():
        err("No seed_state.json found — nothing to clean up.")
        return
    players = json.loads(STATE_FILE.read_text())
    print(f"\n── Deregistering {len(players)} seeded players ──")
    for p in players:
        deregister(client, p)
    STATE_FILE.unlink()
    print("\n  Cleanup complete.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Seed fake players into the Volleyball Scheduler.")
    parser.add_argument("--url", default="http://localhost:8000", help="Backend base URL")
    parser.add_argument("--count", type=int, default=15, help="Number of players to register (max 20)")
    parser.add_argument("--no-queue", action="store_true", help="Register players but don't join queue")
    parser.add_argument("--demo", action="store_true", help="Full demo: register + queue + start + confirm + end")
    parser.add_argument("--cleanup", action="store_true", help="Deregister all seeded players")
    parser.add_argument(
        "--operator-secret",
        default=os.environ.get("OPERATOR_SECRET", "change-me-in-production"),
        help="Operator secret (or set OPERATOR_SECRET env var)",
    )
    args = parser.parse_args()

    args.count = min(args.count, len(PLAYERS))
    base = args.url.rstrip("/") + "/api"
    print(f"\nTarget: {base}")

    with httpx.Client(base_url=base, timeout=15) as client:
        if args.cleanup:
            cmd_cleanup(client)
        elif args.demo:
            cmd_demo(client, args.operator_secret)
        else:
            cmd_seed(client, args.count, join=not args.no_queue)


if __name__ == "__main__":
    main()
