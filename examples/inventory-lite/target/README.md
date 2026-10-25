# inventory-lite target

A small FastAPI inventory service used as a second owned evaluation/rehearsal
fixture. Unlike `payments-lite`, it was authored *after* the platform's scripted
fixtures were fixed — nothing in the agent or check code is shaped around it —
which makes it the honest "unfamiliar repository" for pilot rehearsals.

## API

- `GET /health` — unauthenticated liveness.
- `GET /me` — the workspace resolved from the bearer token.
- `GET /warehouses/{workspace_id}` — a workspace's own warehouse profile.
- `GET /items` — the caller's own items.
- `GET /items/{item_id}` — one item by id.
- `POST /transfers` — move stock out of one of the caller's items.
- `GET /transfers/{transfer_id}` — one transfer by id.

## Behavior

- Every request except `/health` needs `Authorization: Bearer <token>`; the
  seeded fixture tokens are `fixture-token-alice` and `fixture-token-bob`.
- A workspace can only read its own warehouse profile, items and transfers.
- A transfer quantity must never exceed the item's available stock
  (`quantity` minus what is already transferred).
- Quantities are positive integers.
