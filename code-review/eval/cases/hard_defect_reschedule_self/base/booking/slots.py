from dataclasses import dataclass


class Conflict(Exception):
    pass


@dataclass
class Booking:
    id: str
    start: int
    end: int


def overlaps(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    return a_start < b_end and b_start < a_end


def book(calendar: list[Booking], booking: Booking) -> None:
    if booking.end <= booking.start:
        raise ValueError("a booking must end after it starts")
    for other in calendar:
        if overlaps(booking.start, booking.end, other.start, other.end):
            raise Conflict(other.id)
    calendar.append(booking)
