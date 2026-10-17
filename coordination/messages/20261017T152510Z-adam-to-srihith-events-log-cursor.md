# MSG: events/log first page is 500 with next_cursor always null
- ID: `20261017T152510Z-adam-to-srihith-events-log-cursor`
- From: adam
- To: srihith
- Timestamp: 2026-10-17T15:25:10Z
- Kind: ask
- Related subsystem(s): backend, frontend
- Branch / commit / PR or issue link: frontend PR #193 (`feat/adam/event-log-page-note`); backend `GET /assessments/{id}/events/log`
- Summary (facts, not assumptions): `_events_after(..., limit=500)` and `events_log` return `next_cursor: null` even when the first page is full. Project journey and assessment phases only call `after=0`, so a longer log can leave later phases unmarked. #193 surfaces that limit in the UI when `items.length >= 500`. The UI cannot page further until the API exposes a real cursor (or equivalent).
- Action required by recipient: if you can, return a non-null cursor when more events exist after the page; otherwise leave as-is and we keep the honesty note.
