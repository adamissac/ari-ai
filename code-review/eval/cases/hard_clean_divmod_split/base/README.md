# split

Amounts are integer cents.

## Rules

- A bill of `total` cents is split among `people`.
- Everyone pays total // people; the first (total mod people) people pay one
  cent more, so the shares always add up to the total.
