import pytest
from booking.changes import reschedule
from booking.slots import Booking, Conflict


def test_a_booking_can_shift_within_its_own_slot():
    calendar = [Booking("a", 540, 600)]
    try:
        moved = reschedule(calendar, "a", 570, 630)
    except Conflict as exc:
        pytest.fail(f"the booking conflicted with itself: {exc}")
    assert (moved.start, moved.end) == (570, 630)
