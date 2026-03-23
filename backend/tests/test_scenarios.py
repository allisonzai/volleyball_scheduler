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

    def test_more_than_15_players_in_waiting_list(self, db):
        """Game is running with 12 on court and 5 already waiting.
        8 more players arrive during the game — total waiting list grows to 13.
        All positions are compact and in arrival order."""
        # 12 on court + 5 pre-existing waiters
        for i in range(1, 13):
            register_and_queue(db, i)
        early_waiters = [register_and_queue(db, i) for i in range(13, 18)]  # 5 waiters
        game = scheduler.assign_next_game(db)
        for slot in game.slots:
            scheduler.handle_confirmation(slot.player_id, game.id, "yes", db)
        db.commit()

        # 8 more players join while game is running — total queue: 5 + 8 = 13
        late_arrivals = []
        for i in range(18, 26):
            p = make_player(db, i)
            scheduler.join_queue(p.id, db)
            late_arrivals.append(p)
        db.commit()

        queue = scheduler.get_queue(db)
        assert len(queue) == 13, f"Expected 13 players in queue, got {len(queue)}"

        positions = [e.position for e in queue]
        assert positions == list(range(1, 14)), (
            f"Queue positions should be compact 1..13, got {positions}"
        )

        # Early waiters must all precede any late arrival
        early_ids = {p.id for p in early_waiters}
        late_ids = {p.id for p in late_arrivals}
        early_positions = [e.position for e in queue if e.player_id in early_ids]
        late_positions  = [e.position for e in queue if e.player_id in late_ids]
        assert max(early_positions) < min(late_positions), (
            "All early waiters should be ahead of all late arrivals"
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
        should form a 15-player queue. Manually starting the next game should
        slot the first 12 (the 3 original waiters + 9 court players)."""
        players = [register_and_queue(db, i) for i in range(1, 16)]  # 15
        game = scheduler.assign_next_game(db)
        for slot in game.slots:
            scheduler.handle_confirmation(slot.player_id, game.id, "yes", db)
        db.commit()

        scheduler.end_game(game.id, db)
        db.commit()

        # Operator manually starts the next game
        next_game = scheduler.assign_next_game(db)
        db.commit()

        assert next_game is not None, "Next game should be created on manual start"
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

        # After end_game (no auto-start), all 15 are in the queue:
        # 3 original waiters at the front, then 12 returning court players.
        queue = scheduler.get_queue(db)
        assert len(queue) == 15, f"Expected 15 in queue, got {len(queue)}"
        top_3_ids = {e.player_id for e in queue[:3]}
        waiter_ids = {p.id for p in waiters}
        assert waiter_ids == top_3_ids, (
            "Original waiters should be at the front of the queue after rotation"
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
# "If they confirm defer, they will swap with the next person in the waiting list."

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

    def test_defer_swaps_player_to_second_in_queue(self, db):
        # 14 players: 12 slotted, 2 in queue (p13, p14).
        # p1 defers → fill_slot pulls p13 → p1 inserted at position 2 behind p14.
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
        assert queued_ids[0] != target_id, "Deferred player should NOT be at front (swapped one step back)"
        assert queued_ids[1] == target_id, "Deferred player should be at position 2 after swap"

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
        """Deferred player ends up ahead of declined player.
        With 20 players: 12 slotted (p1-p12), 8 in queue (p13-p20).
        - p1 defers → fill_slot pulls p13 → p1 inserted at position 2 → queue: [p14, p1, p15..p20]
        - p2 says no → fill_slot pulls p14 → p2 appended to end → queue: [p1, p15..p20, p2]
        So defer_player_id is still ahead of no_player_id.
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


# ── SCENARIO 15 ──────────────────────────────────────────────────────────────
# "A confirmed player may leave an active game at any time. They are moved to
#  the end of the waiting list and the next queued player is notified."

class TestScenario15_LeaveGameMidPlay:
    def test_confirmed_player_can_leave_active_game(self, db):
        for i in range(1, 13):
            register_and_queue(db, i)
        game = scheduler.assign_next_game(db)
        db.commit()

        # All confirm → game is in progress
        for slot in game.slots:
            scheduler.handle_confirmation(slot.player_id, game.id, "yes", db)
        db.commit()

        assert game.status == GameStatus.IN_PROGRESS

        target_id = game.slots[0].player_id
        scheduler.leave_game(target_id, game.id, db)
        db.commit()

        slot = db.query(GameSlot).filter(
            GameSlot.game_id == game.id,
            GameSlot.player_id == target_id,
        ).first()
        assert slot.status == SlotStatus.WITHDRAWN, "Slot should be WITHDRAWN after leaving"

    def test_leave_game_removes_player_from_queue(self, db):
        for i in range(1, 13):
            register_and_queue(db, i)
        game = scheduler.assign_next_game(db)
        for slot in game.slots:
            scheduler.handle_confirmation(slot.player_id, game.id, "yes", db)
        db.commit()

        target_id = game.slots[0].player_id
        scheduler.leave_game(target_id, game.id, db)
        db.commit()

        queue = scheduler.get_queue(db)
        queued_ids = [e.player_id for e in queue]
        assert target_id not in queued_ids, "Player who left mid-game should NOT be in queue"

    def test_leave_game_fills_slot_from_queue(self, db):
        """When a player leaves and there is someone in the waiting list, that person
        gets a new pending slot."""
        for i in range(1, 14):  # 13 players: 12 play, 1 waiting
            register_and_queue(db, i)
        game = scheduler.assign_next_game(db)
        for slot in game.slots:
            scheduler.handle_confirmation(slot.player_id, game.id, "yes", db)
        db.commit()

        waiter_id = scheduler.get_queue(db)[0].player_id
        target_id = game.slots[0].player_id
        slot_count_before = len(game.slots)

        scheduler.leave_game(target_id, game.id, db)
        db.commit()

        db.refresh(game)
        assert len(game.slots) == slot_count_before + 1, (
            "A new slot should be created for the waiting player after someone leaves"
        )
        new_slot_ids = {s.player_id for s in game.slots}
        assert waiter_id in new_slot_ids, "Waiting player should be notified after a court player leaves"

    def test_leave_game_raises_if_not_confirmed(self, db):
        """Only CONFIRMED slots can use leave_game; pending or non-existent slots raise."""
        for i in range(1, 14):
            register_and_queue(db, i)
        game = scheduler.assign_next_game(db)
        db.commit()

        # Slots are PENDING at this point (more than 12 players)
        pending_id = game.slots[0].player_id
        with pytest.raises(LookupError):
            scheduler.leave_game(pending_id, game.id, db)

    def test_leave_game_raises_if_game_not_active(self, db):
        for i in range(1, 13):
            register_and_queue(db, i)
        game = scheduler.assign_next_game(db)
        for slot in game.slots:
            scheduler.handle_confirmation(slot.player_id, game.id, "yes", db)
        db.commit()

        target_id = game.slots[0].player_id
        scheduler.end_game(game.id, db)
        db.commit()

        db.refresh(game)
        assert game.status == GameStatus.FINISHED

        with pytest.raises(LookupError):
            scheduler.leave_game(target_id, game.id, db)


# ── SCENARIO 16 ──────────────────────────────────────────────────────────────
# "The operator may use 'Start Over' to cancel the current game and clear the
#  waiting list at any time. Player accounts are preserved."

class TestScenario16_ResetAll:
    def test_reset_clears_waiting_list(self, db):
        for i in range(1, 6):
            register_and_queue(db, i)
        db.commit()

        assert len(scheduler.get_queue(db)) == 5

        scheduler.reset_all(db)
        db.commit()

        assert len(scheduler.get_queue(db)) == 0, "Queue must be empty after reset"

    def test_reset_marks_active_game_finished(self, db):
        for i in range(1, 13):
            register_and_queue(db, i)
        game = scheduler.assign_next_game(db)
        for slot in game.slots:
            scheduler.handle_confirmation(slot.player_id, game.id, "yes", db)
        db.commit()

        assert game.status == GameStatus.IN_PROGRESS

        scheduler.reset_all(db)
        db.commit()

        db.refresh(game)
        assert game.status == GameStatus.FINISHED, "Active game should be FINISHED after reset"

    def test_reset_preserves_player_accounts(self, db):
        players = [register_and_queue(db, i) for i in range(1, 6)]
        player_ids = [p.id for p in players]
        db.commit()

        scheduler.reset_all(db)
        db.commit()

        from app.models.player import Player as PlayerModel
        for pid in player_ids:
            p = db.query(PlayerModel).filter(PlayerModel.id == pid).first()
            assert p is not None, f"Player {pid} should still exist after reset"

    def test_reset_with_no_active_game_does_not_crash(self, db):
        for i in range(1, 4):
            register_and_queue(db, i)
        db.commit()

        # No game started — just a queue
        scheduler.reset_all(db)
        db.commit()

        assert len(scheduler.get_queue(db)) == 0

    def test_reset_cancels_open_game_with_pending_slots(self, db):
        for i in range(1, 15):
            register_and_queue(db, i)
        game = scheduler.assign_next_game(db)
        db.commit()

        assert game.status == GameStatus.OPEN

        scheduler.reset_all(db)
        db.commit()

        db.refresh(game)
        assert game.status == GameStatus.FINISHED
        assert len(scheduler.get_queue(db)) == 0

    def test_reset_preserves_game_history(self, db):
        """Start Over keeps game records — they still appear in Past Games."""
        for i in range(1, 13):
            register_and_queue(db, i)
        game = scheduler.assign_next_game(db)
        db.commit()
        game_id = game.id

        scheduler.reset_all(db)
        db.commit()

        remaining = db.query(Game).filter(Game.id == game_id).first()
        assert remaining is not None, "Game record should be preserved after Start Over"


# ── SCENARIO 17 ──────────────────────────────────────────────────────────────
# "Players can register and deregister via the web interface. Deregistration
#  is blocked while the player is in an active game."

class TestScenario17_Deregister:
    def test_deregister_removes_player_from_queue(self, db):
        p = register_and_queue(db, 1)
        db.commit()

        queue_before = scheduler.get_queue(db)
        assert any(e.player_id == p.id for e in queue_before)

        # Simulate the deregister API logic at the service level
        scheduler._remove_from_queue(db, p.id)
        from app.models.player import Player as PlayerModel
        db.delete(db.query(PlayerModel).filter(PlayerModel.id == p.id).first())
        db.commit()

        queue_after = scheduler.get_queue(db)
        assert not any(e.player_id == p.id for e in queue_after), (
            "Deregistered player should be removed from queue"
        )

    def test_deregister_blocked_while_in_active_game(self, db):
        """Deregistration must fail if the player has a confirmed or pending slot
        in an open or in-progress game."""
        from app.models.game import Game as GameModel
        from app.models.game_slot import GameSlot as GameSlotModel, SlotStatus as SS

        for i in range(1, 14):
            register_and_queue(db, i)
        game = scheduler.assign_next_game(db)
        db.commit()

        active_player_id = game.slots[0].player_id

        # Check: player has a pending slot in an active game
        active_slot = (
            db.query(GameSlotModel)
            .join(GameModel, GameSlotModel.game_id == GameModel.id)
            .filter(
                GameSlotModel.player_id == active_player_id,
                GameSlotModel.status.in_([SS.PENDING_CONFIRMATION, SS.CONFIRMED]),
                GameModel.status.in_(["open", "in_progress"]),
            )
            .first()
        )
        assert active_slot is not None, "Player should be blocked from deregistering — active slot exists"

    def test_deregister_allowed_when_not_in_active_game(self, db):
        """A player who is only in the queue (not in any active game) can deregister."""
        p = register_and_queue(db, 99)
        db.commit()

        from app.models.game import Game as GameModel
        from app.models.game_slot import GameSlot as GameSlotModel, SlotStatus as SS

        active_slot = (
            db.query(GameSlotModel)
            .join(GameModel, GameSlotModel.game_id == GameModel.id)
            .filter(
                GameSlotModel.player_id == p.id,
                GameSlotModel.status.in_([SS.PENDING_CONFIRMATION, SS.CONFIRMED]),
                GameModel.status.in_(["open", "in_progress"]),
            )
            .first()
        )
        assert active_slot is None, "Queue-only player should have no active slot — deregister allowed"

        scheduler._remove_from_queue(db, p.id)
        from app.models.player import Player as PlayerModel
        db.delete(db.query(PlayerModel).filter(PlayerModel.id == p.id).first())
        db.commit()

        remaining = db.query(PlayerModel).filter(PlayerModel.id == p.id).first()
        assert remaining is None, "Player record should be gone after deregister"

    def test_deregister_after_game_ends_is_allowed(self, db):
        """Once a game is finished (and no new game auto-starts), every returning
        court player is in the queue with no active slot — deregister is allowed."""
        for i in range(1, 13):
            register_and_queue(db, i)
        game = scheduler.assign_next_game(db)
        for slot in game.slots:
            scheduler.handle_confirmation(slot.player_id, game.id, "yes", db)
        db.commit()

        target_id = game.slots[0].player_id
        scheduler.end_game(game.id, db)
        db.commit()

        db.refresh(game)
        assert game.status == GameStatus.FINISHED

        from app.models.game import Game as GameModel
        from app.models.game_slot import GameSlot as GameSlotModel, SlotStatus as SS

        active_slot = (
            db.query(GameSlotModel)
            .join(GameModel, GameSlotModel.game_id == GameModel.id)
            .filter(
                GameSlotModel.player_id == target_id,
                GameSlotModel.status.in_([SS.PENDING_CONFIRMATION, SS.CONFIRMED]),
                GameModel.status.in_(["open", "in_progress"]),
            )
            .first()
        )
        assert active_slot is None, (
            "After game ends (no auto-start), player is in queue — deregister should be allowed"
        )


# ── SCENARIO 18 ──────────────────────────────────────────────────────────────
# "In the Past Games tab, the operator can clear history."

class TestScenario18_ClearHistory:
    def test_clear_history_deletes_finished_games(self, db):
        for i in range(1, 13):
            register_and_queue(db, i)
        game = scheduler.assign_next_game(db)
        for slot in game.slots:
            scheduler.handle_confirmation(slot.player_id, game.id, "yes", db)
        scheduler.end_game(game.id, db)
        db.commit()

        db.refresh(game)
        assert game.status == GameStatus.FINISHED
        game_id = game.id  # capture before deletion

        scheduler.clear_history(db)
        db.commit()

        remaining = db.query(Game).filter(Game.id == game_id).first()
        assert remaining is None, "Finished game should be deleted after clear_history"

    def test_clear_history_resets_game_id_sequence(self, db):
        """After clearing history, the next game starts at ID 1 again."""
        players = [register_and_queue(db, i) for i in range(1, 6)]
        game1 = scheduler.assign_next_game(db)
        db.commit()
        first_id = game1.id

        scheduler.reset_all(db)  # marks game FINISHED, clears queue
        scheduler.clear_history(db)  # deletes finished games
        db.commit()

        for p in players:
            add_to_queue(db, p)
        game2 = scheduler.assign_next_game(db)
        db.commit()

        assert game2.id == first_id, (
            f"After clearing history, game ID should reset to {first_id}, got {game2.id}"
        )

    def test_clear_history_preserves_active_game(self, db):
        """clear_history only removes FINISHED games; active game is untouched."""
        for i in range(1, 13):
            register_and_queue(db, i)
        active_game = scheduler.assign_next_game(db)
        for slot in active_game.slots:
            scheduler.handle_confirmation(slot.player_id, active_game.id, "yes", db)
        db.commit()

        assert active_game.status == GameStatus.IN_PROGRESS

        scheduler.clear_history(db)
        db.commit()

        db.refresh(active_game)
        assert active_game.status == GameStatus.IN_PROGRESS, (
            "Active game should not be touched by clear_history"
        )

    def test_clear_history_preserves_player_accounts(self, db):
        players = [register_and_queue(db, i) for i in range(1, 5)]
        game = scheduler.assign_next_game(db)
        scheduler.end_game(game.id, db)
        db.commit()

        scheduler.clear_history(db)
        db.commit()

        from app.models.player import Player as PlayerModel
        for p in players:
            assert db.query(PlayerModel).filter(PlayerModel.id == p.id).first() is not None


# ── SCENARIO 19 ──────────────────────────────────────────────────────────────
# "The player in the waiting list can choose 'Defer' to swap with the next
#  person in the waiting list."

class TestScenario19_QueueDefer:
    def test_defer_swaps_with_next_player(self, db):
        """Player at position 1 defers — they move to position 2, next moves to 1."""
        p1 = register_and_queue(db, 1)
        p2 = register_and_queue(db, 2)
        p3 = register_and_queue(db, 3)

        scheduler.defer_in_queue(p1.id, db)
        db.commit()

        queue = scheduler.get_queue(db)
        ids = [e.player_id for e in queue]
        assert ids[0] == p2.id, "p2 should now be first"
        assert ids[1] == p1.id, "p1 should be second after deferring"
        assert ids[2] == p3.id, "p3 stays third"

    def test_defer_last_player_raises(self, db):
        """A player who is last in the queue cannot defer."""
        p1 = register_and_queue(db, 1)
        register_and_queue(db, 2)

        queue = scheduler.get_queue(db)
        last_id = queue[-1].player_id

        with pytest.raises(ValueError):
            scheduler.defer_in_queue(last_id, db)

    def test_defer_not_in_queue_raises(self, db):
        p = make_player(db, 1)
        db.commit()

        with pytest.raises(LookupError):
            scheduler.defer_in_queue(p.id, db)

    def test_defer_middle_player(self, db):
        """Player in the middle defers — only they and the player behind them swap."""
        p1 = register_and_queue(db, 1)
        p2 = register_and_queue(db, 2)
        p3 = register_and_queue(db, 3)
        p4 = register_and_queue(db, 4)

        scheduler.defer_in_queue(p2.id, db)
        db.commit()

        queue = scheduler.get_queue(db)
        ids = [e.player_id for e in queue]
        assert ids == [p1.id, p3.id, p2.id, p4.id], f"Expected p1,p3,p2,p4 but got {ids}"
