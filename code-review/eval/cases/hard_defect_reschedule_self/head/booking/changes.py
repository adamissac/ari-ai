from booking.slots import Booking, Conflict, find, overlaps


def reschedule(calendar: list[Booking], booking_id: str, start: int, end: int) -> Booking:
    if end <= start:
        raise ValueError("a booking must end after it starts")
    current = find(calendar, booking_id)
    for other in calendar:
        if overlaps(start, end, other.start, other.end):
            raise Conflict(other.id)
    current.start, current.end = start, end
    return current
