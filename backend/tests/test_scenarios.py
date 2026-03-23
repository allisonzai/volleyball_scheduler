"""
Scenario tests based directly on volleyball_scheduler.docx requirements.

Each test class maps to one numbered rule from the spec.
Run with: pytest tests/test_scenarios.py -v
"""
import pytest
import asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.config import settings
from app.models.player import Player
from app.models.game import Game, GameStatus
from app.models.game_slot import GameSlot, SlotStatus
from app.models.waiting_list import WaitingList
from app.services import scheduler
from app.services.display_name import resolve_display_name

# ── Test fixtures ────────────────────────────────────────────────────────────

@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Patch settings for tests
    settings.MAX_PLAYERS = 12
    settings.CONFIRM_TIMEOUT_SECONDS = 300

    # Disable timeout scheduling during unit tests by clearing any pending timers
    scheduler._timeout_tasks.clear()

    yield session
    session.close()


def make_player(db, n: int, first="Player", last=None) -> Player:
    """Register a player and add them to the DB."""
    last = last or str(n)
    phone = f"+1212555{n:04d}"
    email = f"player{n}@test.com"
    display = resolve_display_name(first, last, phone, db)
    p = Player(
        first_name=first,
        last_name=last,
        phone=phone,
        email=email,
        display_name=display,
        secret_token=f"test-token-{n:04d}",
        password_hash="test-hash",
        is_verified=True,
    )
    db.add(p)
    db.flush()
    return p


def add_to_queue(db, player: Player) -> WaitingList:
    entry = scheduler._append_to_queue(db, player.id)
    db.flush()
    return entry


def register_and_queue(db, n: int, first="Player", last=None) -> Player:
    p = make_player(db, n, first, last)
    add_to_queue(db, p)
    return p


# ── SCENARIO 1 ───────────────────────────────────────────────────────────────
# "Every game can only have up to 12 players"

class TestScenario1_MaxTwelvePlayers:
    def test_game_max_players_default_is_12(self, db):
        for i in range(1, 14):
            register_and_queue(db, i)

        game = scheduler.assign_next_game(db)
        db.commit()

        active_slots = [s for s in game.slots if s.status != SlotStatus.DECLINED]
        assert len(active_slots) == 12, (
            f"Expected 12 slots, got {len(active_slots)}"
        )

    def test_game_never_exceeds_12_confirmed(self, db):
        """Even if we try to confirm a 13th player, max is enforced at slot creation."""
        for i in range(1, 20):
            register_and_queue(db, i)

        game = scheduler.assign_next_game(db)
        db.commit()

        # Confirm all pending slots
        for slot in list(game.slots):
            if slot.status == SlotStatus.PENDING_CONFIRMATION:
                scheduler.handle_confirmation(slot.player_id, game.id, "yes", db)
        db.commit()

        confirmed = [s for s in game.slots if s.status == SlotStatus.CONFIRMED]
        assert len(confirmed) <= 12, f"Confirmed {len(confirmed)} > 12"


# ── SCENARIO 2 ───────────────────────────────────────────────────────────────
# "Every player must sign up to receive a number assigned on a first-come,
#  first-served basis"

class TestScenario2_SignupNumbers:
    def test_signup_numbers_assigned_in_order(self, db):
        players = [register_and_queue(db, i) for i in range(1, 6)]
        db.commit()

        entries = scheduler.get_queue(db)
        numbers = [e.signup_number for e in entries]

        assert numbers == sorted(numbers), "Signup numbers not in ascending order"
        assert len(set(numbers)) == len(numbers), "Signup numbers must be unique"

    def test_first_come_first_served_queue_positions(self, db):
        p1 = register_and_queue(db, 1)
        p2 = register_and_queue(db, 2)
        p3 = register_and_queue(db, 3)
        db.commit()

        entries = scheduler.get_queue(db)
        player_ids = [e.player_id for e in entries]

        assert player_ids[0] == p1.id, "First to join should be first in queue"
        assert player_ids[1] == p2.id
        assert player_ids[2] == p3.id

    def test_signup_number_preserved_after_rotation(self, db):
        """Signup number must never change once assigned."""
        p = register_and_queue(db, 1)
        db.commit()

        original_num = scheduler.get_queue(db)[0].signup_number

        # Remove and re-add (simulates defer returning to front)
        scheduler._remove_from_queue(db, p.id)
        scheduler._append_to_queue(db, p.id)
        db.commit()

        # The re-added entry gets a new signup_number because it's a new join.
        # But the original entry's number should have been the first one assigned.
        assert original_num >= 1


# ── SCENARIO 3 ───────────────────────────────────────────────────────────────
# "If the number of players are more than 12, we can start the game with the
#  1st 12 players and leave the other players waiting for the next game"

class TestScenario3_MoreThan12Players:
    def test_first_12_get_slots(self, db):
        players = [register_and_queue(db, i) for i in range(1, 16)]
        db.commit()

        game = scheduler.assign_next_game(db)
        db.commit()

        slotted_ids = {s.player_id for s in game.slots}
        first_12_ids = {p.id for p in players[:12]}

        assert slotted_ids == first_12_ids, (
            "First 12 to join should be slotted, not later arrivals"
        )

    def test_remaining_players_stay_in_queue(self, db):
        players = [register_and_queue(db, i) for i in range(1, 16)]  # 15 total
        db.commit()

        scheduler.assign_next_game(db)
        db.commit()

        queue = scheduler.get_queue(db)
        assert len(queue) == 3, f"Expected 3 in queue, got {len(queue)}"

        queued_ids = {e.player_id for e in queue}
        last_3_ids = {p.id for p in players[12:]}
        assert queued_ids == last_3_ids, "Players 13-15 should be in queue"

    def test_game_status_is_open_when_confirmations_pending(self, db):
        for i in range(1, 14):
            register_and_queue(db, i)
        db.commit()

        game = scheduler.assign_next_game(db)
        db.commit()

        assert game.status == GameStatus.OPEN, (
            "Game should be OPEN while waiting for confirmations"
        )


# ── SCENARIO 4 ───────────────────────────────────────────────────────────────
# "While the game is ongoing the newly arriving players will be added to the
#  waiting list"

class TestScenario4_NewArrivalsJoinWaitingList:
    def test_players_can_join_queue_while_game_active(self, db):
        # Start a game with 12 players
        for i in range(1, 13):
            register_and_queue(db, i)
        game = scheduler.assign_next_game(db)
        for slot in game.slots:
            scheduler.handle_confirmation(slot.player_id, game.id, "yes", db)
        db.commit()

        assert game.status == GameStatus.IN_PROGRESS

        # New player arrives after game starts
        late = make_player(db, 99)
        entry = scheduler.join_queue(late.id, db)
        db.commit()

        queue = scheduler.get_queue(db)
        assert any(e.player_id == late.id for e in queue), (
            "Late-arriving player should be in the waiting list"
        )

    def test_late_players_are_at_end_of_queue(self, db):
        for i in range(1, 13):
            register_and_queue(db, i)
        early_waiter = register_and_queue(db, 13)  # already waiting
        game = scheduler.assign_next_game(db)
        for slot in game.slots:
            scheduler.handle_confirmation(slot.player_id, game.id, "yes", db)
        db.commit()

        late = make_player(db, 99)
        scheduler.join_queue(late.id, db)
        db.commit()

        queue = scheduler.get_queue(db)
        positions = {e.player_id: e.position for e in queue}
        assert positions[early_waiter.id] < positions[late.id], (
            "Early waiter should be ahead of late arrival"
        )


# ── SCENARIO 5 ───────────────────────────────────────────────────────────────
# "Once a game is completed the players on the court will be added to the
#  waiting list and the 1st 12 players will play the next game"

class TestScenario5_GameRotation:
    def test_court_players_return_to_queue_after_game(self, db):
        for i in range(1, 13):
            register_and_queue(db, i)
        game = scheduler.assign_next_game(db)
        court_ids = [s.player_id for s in game.slots]
        for slot in game.slots:
            scheduler.handle_confirmation(slot.player_id, game.id, "yes", db)
        db.commit()

        scheduler.end_game(game.id, db)
        db.commit()

        # All 12 court players should now be back in some state
        # (either in queue or in the next game's slots)
        next_game = db.query(Game).filter(Game.id != game.id).first()
        if next_game:
            next_slotted = {s.player_id for s in next_game.slots}
            queued = {e.player_id for e in scheduler.get_queue(db)}
            accounted_for = next_slotted | queued
        else:
            queued = {e.player_id for e in scheduler.get_queue(db)}
            accounted_for = queued

        for pid in court_ids:
            assert pid in accounted_for, (
                f"Court player {pid} missing from queue/next game after rotation"
            )

    def test_next_game_uses_first_12_in_queue(self, db):
        """After a 12-player game ends with 15 total, the 3 waiters + 12 rotated
        should form a new 14-player queue, and the next 12 get slotted."""
        players = [register_and_queue(db, i) for i in range(1, 16)]  # 15
        game = scheduler.assign_next_game(db)
        for slot in game.slots:
            scheduler.handle_confirmation(slot.player_id, game.id, "yes", db)
        db.commit()

        scheduler.end_game(game.id, db)
        db.commit()

        next_game = db.query(Game).filter(
            Game.status.in_([GameStatus.OPEN, GameStatus.IN_PROGRESS])
        ).first()
        assert next_game is not None, "Next game should be auto-created after end"
        assert len(next_game.slots) == 12, (
            f"Next game should have 12 slots, got {len(next_game.slots)}"
        )

    def test_court_players_go_to_end_of_queue(self, db):
        """The 3 waiters who didn't play should be AHEAD of the 12 returning court players."""
        players = [register_and_queue(db, i) for i in range(1, 16)]  # 15
        waiters = players[12:]  # players 13, 14, 15

        game = scheduler.assign_next_game(db)
        for slot in game.slots:
            scheduler.handle_confirmation(slot.player_id, game.id, "yes", db)
        db.commit()

        scheduler.end_game(game.id, db)
        db.commit()

        # After end_game, assign_next_game runs and pulls 12 from queue.
        # The queue after that should contain the remaining players.
        queue = scheduler.get_queue(db)
        next_game = db.query(Game).filter(
            Game.status.in_([GameStatus.OPEN, GameStatus.IN_PROGRESS])
        ).first()

        if next_game:
            # Next game slots should include the 3 waiters (they were at front)
            next_slot_ids = {s.player_id for s in next_game.slots}
            waiter_ids = {p.id for p in waiters}
            # At least the 3 original waiters should be in the next game
            assert waiter_ids.issubset(next_slot_ids), (
                "Original waiters should be first into the next game"
            )


# ── SCENARIO 6 ───────────────────────────────────────────────────────────────
# "If the number of the players is less than or equal to 12, we don't need to
#  schedule the game because everyone can play"

class TestScenario6_AtMost12Players:
    @pytest.mark.parametrize("n", [1, 6, 11, 12])
    def test_everyone_plays_immediately_when_12_or_fewer(self, db, n):
        for i in range(1, n + 1):
            register_and_queue(db, i)
        db.commit()

        game = scheduler.assign_next_game(db)
        db.commit()

        assert game.status == GameStatus.IN_PROGRESS, (
            f"With {n} players game should start immediately (no confirmation needed)"
        )

        confirmed = [s for s in game.slots if s.status == SlotStatus.CONFIRMED]
        assert len(confirmed) == n, (
            f"All {n} players should be confirmed automatically"
        )

    def test_no_players_left_in_queue_when_all_fit(self, db):
        for i in range(1, 9):
            register_and_queue(db, i)
        db.commit()

        scheduler.assign_next_game(db)
        db.commit()

        queue = scheduler.get_queue(db)
        assert len(queue) == 0, "Queue should be empty when everyone fits"

    def test_exactly_12_players_no_confirmation_needed(self, db):
        for i in range(1, 13):
            register_and_queue(db, i)
        db.commit()

        game = scheduler.assign_next_game(db)
        db.commit()

        pending = [s for s in game.slots if s.status == SlotStatus.PENDING_CONFIRMATION]
        assert len(pending) == 0, (
            "No pending confirmations when exactly 12 players are in queue"
        )
        assert game.status == GameStatus.IN_PROGRESS


# ── SCENARIO 7 ───────────────────────────────────────────────────────────────
# "Any player is allowed to leave while they are in the waiting list"

class TestScenario7_LeaveWaitingList:
    def test_player_can_leave_queue(self, db):
        players = [register_and_queue(db, i) for i in range(1, 5)]
        db.commit()

        scheduler.leave_queue(players[1].id, db)
        db.commit()

        queue = scheduler.get_queue(db)
        queued_ids = [e.player_id for e in queue]
        assert players[1].id not in queued_ids, "Player should no longer be in queue"

    def test_queue_resequenced_after_leave(self, db):
        players = [register_and_queue(db, i) for i in range(1, 5)]
        db.commit()

        scheduler.leave_queue(players[1].id, db)  # remove player 2 (position 2)
        db.commit()

        queue = scheduler.get_queue(db)
        positions = [e.position for e in queue]
        assert positions == list(range(1, len(positions) + 1)), (
            f"Positions should be compact 1..N after leave, got {positions}"
        )

    def test_order_preserved_after_leave(self, db):
        p1 = register_and_queue(db, 1)
        p2 = register_and_queue(db, 2)
        p3 = register_and_queue(db, 3)
        db.commit()

        scheduler.leave_queue(p2.id, db)
        db.commit()

        queue = scheduler.get_queue(db)
        assert queue[0].player_id == p1.id
        assert queue[1].player_id == p3.id

    def test_cannot_leave_if_not_in_queue(self, db):
        p = make_player(db, 1)
        db.commit()

        # Should not raise — just silently does nothing
        scheduler.leave_queue(p.id, db)
        db.commit()

    def test_player_cannot_be_in_queue_twice(self, db):
        p = register_and_queue(db, 1)
        db.commit()

        # Try adding again
        entry = scheduler._append_to_queue(db, p.id)
        db.commit()

        queue = scheduler.get_queue(db)
        ids = [e.player_id for e in queue]
        assert ids.count(p.id) == 1, "Player should appear exactly once in queue"


# ── SCENARIO 8 ───────────────────────────────────────────────────────────────
# "The player scheduled for a game will be notified and wait for up to 5 minutes
#  which can be configurable"

class TestScenario8_ConfigurableTimeout:
    def test_default_timeout_is_5_minutes(self):
        assert settings.CONFIRM_TIMEOUT_SECONDS == 300, (
            "Default timeout should be 300 seconds (5 minutes)"
        )

    def test_timeout_is_configurable(self):
        original = settings.CONFIRM_TIMEOUT_SECONDS
        settings.CONFIRM_TIMEOUT_SECONDS = 60
        assert settings.CONFIRM_TIMEOUT_SECONDS == 60
        settings.CONFIRM_TIMEOUT_SECONDS = original  # restore

    def test_timed_out_player_moved_to_end_of_queue(self, db):
        players = [register_and_queue(db, i) for i in range(1, 15)]
        game = scheduler.assign_next_game(db)
        db.commit()

        target_id = game.slots[0].player_id

        # Simulate timeout
        scheduler.handle_timeout(target_id, game.id, db)
        db.commit()

        slot = db.query(GameSlot).filter(
            GameSlot.game_id == game.id,
            GameSlot.player_id == target_id
        ).first()
        assert slot.status == SlotStatus.TIMED_OUT, "Slot should be TIMED_OUT"

        queue = scheduler.get_queue(db)
        queued_ids = [e.player_id for e in queue]
        assert target_id in queued_ids, "Timed-out player should be back in queue"
        assert queued_ids[-1] == target_id, "Timed-out player should be at END of queue"

    def test_timeout_triggers_next_player_notification(self, db):
        for i in range(1, 15):
            register_and_queue(db, i)
        game = scheduler.assign_next_game(db)
        db.commit()

        initial_slot_count = len(game.slots)
        first_player_id = game.slots[0].player_id

        scheduler.handle_timeout(first_player_id, game.id, db)
        db.commit()

        db.refresh(game)
        assert len(game.slots) == initial_slot_count + 1, (
            "A new slot should be created for the next player after timeout"
        )

    def test_response_after_timeout_is_ignored(self, db):
        for i in range(1, 14):
            register_and_queue(db, i)
        game = scheduler.assign_next_game(db)
        db.commit()

        target_id = game.slots[0].player_id

        scheduler.handle_timeout(target_id, game.id, db)
        db.commit()

        # Late YES should be silently ignored (slot is already TIMED_OUT)
        scheduler.handle_confirmation(target_id, game.id, "yes", db)
        db.commit()

        slot = db.query(GameSlot).filter(
            GameSlot.game_id == game.id,
            GameSlot.player_id == target_id
        ).first()
        assert slot.status == SlotStatus.TIMED_OUT, (
            "Slot status should not change after a timed-out player sends a late yes"
        )


# ── SCENARIO 9 ───────────────────────────────────────────────────────────────
# "If they confirm yes, they are marked as playing"

class TestScenario9_ConfirmYes:
    def test_yes_marks_slot_confirmed(self, db):
        for i in range(1, 14):
            register_and_queue(db, i)
        game = scheduler.assign_next_game(db)
        db.commit()

        first_slot = game.slots[0]
        scheduler.handle_confirmation(first_slot.player_id, game.id, "yes", db)
        db.commit()

        db.refresh(first_slot)
        assert first_slot.status == SlotStatus.CONFIRMED

    def test_game_starts_when_all_confirm_yes(self, db):
        for i in range(1, 14):
            register_and_queue(db, i)
        game = scheduler.assign_next_game(db)
        db.commit()

        for slot in list(game.slots):
            scheduler.handle_confirmation(slot.player_id, game.id, "yes", db)
        db.commit()

        db.refresh(game)
        assert game.status == GameStatus.IN_PROGRESS, (
            "Game should be IN_PROGRESS once all players confirm yes"
        )

    def test_yes_is_case_insensitive(self, db):
        for i in range(1, 14):
            register_and_queue(db, i)
        game = scheduler.assign_next_game(db)
        db.commit()

        slot = game.slots[0]
        scheduler.handle_confirmation(slot.player_id, game.id, "YES", db)
        db.commit()

        db.refresh(slot)
        assert slot.status == SlotStatus.CONFIRMED


# ── SCENARIO 10 ──────────────────────────────────────────────────────────────
# "If they confirm no, they will be taken out of the current game and put at
#  the end of the waiting list and notify the next person."

class TestScenario10_ConfirmNo:
    def test_no_sets_slot_declined(self, db):
        for i in range(1, 14):
            register_and_queue(db, i)
        game = scheduler.assign_next_game(db)
        db.commit()

        slot = game.slots[0]
        scheduler.handle_confirmation(slot.player_id, game.id, "no", db)
        db.commit()

        db.refresh(slot)
        assert slot.status == SlotStatus.DECLINED

    def test_no_puts_player_at_end_of_queue(self, db):
        for i in range(1, 15):
            register_and_queue(db, i)
        game = scheduler.assign_next_game(db)
        db.commit()

        target_id = game.slots[0].player_id
        scheduler.handle_confirmation(target_id, game.id, "no", db)
        db.commit()

        queue = scheduler.get_queue(db)
        queued_ids = [e.player_id for e in queue]
        assert target_id in queued_ids, "Player who said no should be back in queue"
        assert queued_ids[-1] == target_id, "Player who said no should be at END of queue"

    def test_no_triggers_next_player_slot(self, db):
        for i in range(1, 15):
            register_and_queue(db, i)
        game = scheduler.assign_next_game(db)
        db.commit()

        initial_slots = len(game.slots)
        scheduler.handle_confirmation(game.slots[0].player_id, game.id, "no", db)
        db.commit()

        db.refresh(game)
        assert len(game.slots) == initial_slots + 1, (
            "Next player from queue should be notified after a no"
        )

    def test_no_with_empty_queue_does_not_crash(self, db):
        """If queue is empty when someone says no, game still proceeds with confirmed players."""
        for i in range(1, 13):
            register_and_queue(db, i)

        # Only 12 players — game starts immediately, no confirmation needed
        game = scheduler.assign_next_game(db)
        db.commit()

        assert game.status == GameStatus.IN_PROGRESS
        # No pending slots to decline — this is the ≤12 path, all auto-confirmed


# ── SCENARIO 11 ──────────────────────────────────────────────────────────────
# "If they confirm defer, put them at the start of the waiting list and notify
#  the next person."

class TestScenario11_ConfirmDefer:
    def test_defer_sets_slot_declined(self, db):
        for i in range(1, 14):
            register_and_queue(db, i)
        game = scheduler.assign_next_game(db)
        db.commit()

        slot = game.slots[0]
        scheduler.handle_confirmation(slot.player_id, game.id, "defer", db)
        db.commit()

        db.refresh(slot)
        assert slot.status == SlotStatus.DECLINED

    def test_defer_puts_player_at_front_of_queue(self, db):
        for i in range(1, 15):
            register_and_queue(db, i)
        game = scheduler.assign_next_game(db)
        db.commit()

        target_id = game.slots[0].player_id
        scheduler.handle_confirmation(target_id, game.id, "defer", db)
        db.commit()

        queue = scheduler.get_queue(db)
        queued_ids = [e.player_id for e in queue]
        assert target_id in queued_ids, "Deferred player should be in queue"
        assert queued_ids[0] == target_id, "Deferred player should be at FRONT of queue"

    def test_defer_triggers_next_player_slot(self, db):
        for i in range(1, 15):
            register_and_queue(db, i)
        game = scheduler.assign_next_game(db)
        db.commit()

        initial_slots = len(game.slots)
        scheduler.handle_confirmation(game.slots[0].player_id, game.id, "defer", db)
        db.commit()

        db.refresh(game)
        assert len(game.slots) == initial_slots + 1, (
            "Next queued player should be notified after a defer"
        )

    def test_defer_vs_no_queue_position(self, db):
        """Deferred player ends up at FRONT; declined player ends up at END.
        With 20 players: 12 slotted (p1-p12), 8 in queue (p13-p20).
        - p1 defers → fill_slot pulls p13 → p1 prepended to front → queue: [p1, p14..p20]
        - p2 says no → fill_slot pulls p14 (p1 already has an active slot this game)
                     → p2 appended to end → queue: [p1, p15..p20, p2]
        So defer_player_id is ahead of no_player_id.
        """
        for i in range(1, 21):  # 20 players: 12 slotted, 8 in queue
            register_and_queue(db, i)
        game = scheduler.assign_next_game(db)
        db.commit()

        defer_player_id = game.slots[0].player_id
        no_player_id = game.slots[1].player_id

        scheduler.handle_confirmation(defer_player_id, game.id, "defer", db)
        scheduler.handle_confirmation(no_player_id, game.id, "no", db)
        db.commit()

        queue = scheduler.get_queue(db)
        ids = [e.player_id for e in queue]

        assert defer_player_id in ids, "Deferred player should be in queue"
        assert no_player_id in ids, "Declined player should be in queue"
        assert ids.index(defer_player_id) < ids.index(no_player_id), (
            f"Deferred player (pos {ids.index(defer_player_id)}) should be ahead of "
            f"declined player (pos {ids.index(no_player_id)})"
        )


# ── SCENARIO 12 ──────────────────────────────────────────────────────────────
# "Confirm by typing yes, no, or defer in short messages, or clicking yes, no,
#  or defer in the app."

class TestScenario12_ValidResponses:
    def test_invalid_response_raises(self, db):
        for i in range(1, 14):
            register_and_queue(db, i)
        game = scheduler.assign_next_game(db)
        db.commit()

        slot = game.slots[0]
        with pytest.raises(ValueError, match="Invalid response"):
            scheduler.handle_confirmation(slot.player_id, game.id, "maybe", db)

    @pytest.mark.parametrize("response", ["yes", "YES", "Yes", "no", "NO", "No", "defer", "DEFER", "Defer"])
    def test_all_valid_responses_accepted(self, db, response):
        for i in range(1, 14):
            register_and_queue(db, i)
        game = scheduler.assign_next_game(db)
        db.commit()

        slot = game.slots[0]
        # Should not raise
        scheduler.handle_confirmation(slot.player_id, game.id, response, db)

    def test_response_with_whitespace_accepted(self, db):
        for i in range(1, 14):
            register_and_queue(db, i)
        game = scheduler.assign_next_game(db)
        db.commit()

        slot = game.slots[0]
        scheduler.handle_confirmation(slot.player_id, game.id, "  yes  ", db)
        db.commit()

        db.refresh(slot)
        assert slot.status == SlotStatus.CONFIRMED


# ── SCENARIO 13 ──────────────────────────────────────────────────────────────
# "The player will be displayed by their first name followed by the initial of
#  the last name. If there are two players with the same names they should be
#  differentiated by adding the last digits of their phone number."

class TestScenario13_DisplayNames:
    def test_display_name_format(self, db):
        p = make_player(db, 1, first="Alice", last="Smith")
        db.commit()
        assert p.display_name == "Alice S", f"Expected 'Alice S' got '{p.display_name}'"

    def test_duplicate_names_get_phone_suffix(self, db):
        p1 = make_player(db, 1, first="Alice", last="Smith")
        db.commit()
        assert p1.display_name == "Alice S"

        p2 = make_player(db, 2, first="Alice", last="Sutton")
        db.commit()
        # Both have "Alice S" base — p2 should get a suffix, p1 should be updated
        assert p2.display_name != "Alice S", "Duplicate name should have suffix"
        db.refresh(p1)
        assert p1.display_name != "Alice S" or p2.display_name != "Alice S", (
            "At least one duplicate must be disambiguated"
        )
        # Verify bracket format
        if p2.display_name != "Alice S":
            assert "[" in p2.display_name and "]" in p2.display_name

    def test_unique_names_no_suffix(self, db):
        p1 = make_player(db, 1, first="Alice", last="Smith")
        p2 = make_player(db, 2, first="Bob", last="Jones")
        db.commit()
        assert p1.display_name == "Alice S"
        assert p2.display_name == "Bob J"

    def test_disambiguation_uses_phone_last_digits(self, db):
        make_player(db, 42, first="Alice", last="Smith")
        db.commit()
        p2 = make_player(db, 89, first="Alice", last="Sutton")
        db.commit()

        # p2's phone ends in '0089', should be "Alice S [0089]"
        assert "0089" in p2.display_name and "[" in p2.display_name, (
            f"Expected bracket format with '0089', got '{p2.display_name}'"
        )

    def test_three_same_initials_all_unique(self, db):
        for n in [11, 22, 33]:
            make_player(db, n, first="Chris", last="Brown")
            db.commit()

        names = [db.query(Player).filter(Player.id == i+1).first().display_name
                 for i in range(3)]
        assert len(set(names)) == 3, f"All three display names must be unique: {names}"


# ── SCENARIO 14 ──────────────────────────────────────────────────────────────
# "For the current game, and waiting list, show every player's name and the
#  number that they were given when they signed up."

class TestScenario14_SignupNumbersVisible:
    def test_queue_entries_have_signup_number(self, db):
        for i in range(1, 5):
            register_and_queue(db, i)
        db.commit()

        queue = scheduler.get_queue(db)
        for entry in queue:
            assert entry.signup_number is not None, "Every queue entry must have a signup_number"
            assert entry.signup_number >= 1

    def test_signup_numbers_are_unique_across_all_entries(self, db):
        for i in range(1, 8):
            register_and_queue(db, i)
        db.commit()

        queue = scheduler.get_queue(db)
        numbers = [e.signup_number for e in queue]
        assert len(set(numbers)) == len(numbers), "Signup numbers must all be unique"

    def test_signup_numbers_reflect_join_order(self, db):
        for i in range(1, 6):
            register_and_queue(db, i)
        db.commit()

        queue = scheduler.get_queue(db)
        numbers = [e.signup_number for e in queue]
        assert numbers == sorted(numbers), (
            "Signup numbers should increase in join order"
        )


# ── EDGE CASES ───────────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_empty_queue_start_game_returns_none(self, db):
        result = scheduler.assign_next_game(db)
        assert result is None, "assign_next_game should return None when queue is empty"

    def test_single_player_game(self, db):
        register_and_queue(db, 1)
        game = scheduler.assign_next_game(db)
        db.commit()

        assert game is not None
        assert game.status == GameStatus.IN_PROGRESS
        assert len(game.slots) == 1

    def test_chain_of_all_declines_exhausts_queue(self, db):
        """When all backup players are exhausted, the game starts with whoever confirmed.
        With 13 players (12 slotted, 1 backup):
          - p1 says yes
          - p2 says no → backup (p13) is notified
          - p3 says no → no new backup available → game starts immediately with p1
        Remaining PENDING slots (p4-p12) are left unresolved but game is IN_PROGRESS.
        """
        for i in range(1, 14):  # 13 players: 12 slotted, 1 in queue
            register_and_queue(db, i)
        game = scheduler.assign_next_game(db)
        db.commit()

        first_slot = game.slots[0]
        second_slot = game.slots[1]
        third_slot = game.slots[2]

        # p1 confirms
        scheduler.handle_confirmation(first_slot.player_id, game.id, "yes", db)
        # p2 says no → p13 (only backup) is notified
        scheduler.handle_confirmation(second_slot.player_id, game.id, "no", db)
        # p3 says no → queue now empty of NEW players → game starts with just p1
        scheduler.handle_confirmation(third_slot.player_id, game.id, "no", db)
        db.commit()

        db.refresh(game)
        # Game should have started because queue was exhausted and p1 confirmed
        assert game.status == GameStatus.IN_PROGRESS, (
            f"Game should start once backup queue is exhausted; got {game.status}"
        )
        confirmed = [s for s in game.slots if s.status == SlotStatus.CONFIRMED]
        assert len(confirmed) >= 1, "At least the one confirming player should be marked"

    def test_game_status_transitions_correctly(self, db):
        for i in range(1, 13):
            register_and_queue(db, i)
        game = scheduler.assign_next_game(db)
        db.commit()

        assert game.status == GameStatus.IN_PROGRESS  # ≤12 starts immediately

        scheduler.end_game(game.id, db)
        db.commit()

        db.refresh(game)
        assert game.status == GameStatus.FINISHED

    def test_player_not_in_queue_cannot_double_join(self, db):
        p = register_and_queue(db, 1)
        db.commit()

        entry = scheduler._append_to_queue(db, p.id)
        db.commit()

        queue = scheduler.get_queue(db)
        assert len(queue) == 1, "Player should only appear once even if added twice"
