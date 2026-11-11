import pytest
from booking.changes import reschedule
from booking.slots import Booking, Conflict


def test_move_to_a_free_slot():
    calendar = [Booking("a", 540, 600), Booking("b", 600, 660)]
    moved = reschedule(calendar, "a", 720, 780)
    assert (moved.start, moved.end) == (720, 780)


def test_move_onto_another_booking_conflicts():
    calendar = [Booking("a", 540, 600), Booking("b", 600, 660)]
    with pytest.raises(Conflict):
        reschedule(calendar, "a", 630, 690)


def test_unknown_booking():
    with pytest.raises(KeyError):
        reschedule([], "nope", 0, 30)
