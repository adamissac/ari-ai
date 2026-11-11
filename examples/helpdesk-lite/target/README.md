# helpdesk-lite

A small support desk API. Agents belong to an organization and work that
organization's tickets and customers.

## Behavior

- Every endpoint except `/health` requires a valid agent token
  (`Authorization: Bearer <token>`).
- An agent can only read tickets, attachments and customers that belong to their own
  organization. Anything else answers 404, as if it did not exist.
- Search returns only records of the caller's organization, whatever the search text is.
- Help articles are shared by all organizations. The article endpoint serves files from the
  article folder and nothing else.
- Exports are per organization. The export endpoint serves files from the caller's own
  export folder and nothing else.
- Only admins can list an organization's agents.

## Layout

- `helpdesk_lite/app.py` builds the app and mounts the routers.
- `helpdesk_lite/auth.py` resolves the caller; `access.py` holds the visibility rules.
- `helpdesk_lite/store.py` holds the seeded data (objects plus a SQLite search index).
- `helpdesk_lite/routers/` has one module per area.

## Run

    pip install -e ".[dev]"
    uvicorn --factory helpdesk_lite.app:create_app
    pytest -q
