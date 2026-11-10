# booking

Times are minutes since midnight. A booking covers the half-open range
[start, end).

## Rules

- Two bookings conflict when their ranges overlap. Back-to-back bookings
  (one ends when the next starts) do not conflict.
- A booking can be moved to any slot that is free of *other* bookings. Moving a
  booking to a slot that overlaps its own current slot is allowed.
