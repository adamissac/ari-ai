import pytest
from booking.slots import Booking, Conflict, book


def test_back_to_back_bookings_do_not_conflict():
    calendar = [Booking("a", 540, 600)]
    book(calendar, Booking("b", 600, 660))
    assert len(calendar) == 2


def test_overlap_conflicts():
    calendar = [Booking("a", 540, 600)]
    with pytest.raises(Conflict):
        book(calendar, Booking("b", 570, 630))
