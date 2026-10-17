# MSG: Frontend transport ready; real HTTP/PostgreSQL proof

- From: sarosh
- To: vihaan, srihith, adam; cc sai
- Kind: integration / handoff
- Timestamp (UTC): 2026-10-17T03:03:08Z
- Commits: `d4a0fce`, `3bc4e28`, `05ce162`, `a48a202` (main, per explicit user direction)
- Issue: #29

`frontend/transport/**` now provides ApiClient + watchAssessment using generated
shared TS/JSON schemas (0.5.0), no model/schema copies or app scaffold changes.
Consume `file:./transport` from the future frontend root manifest after building.
Session cookie/CSRF, lists/logout, explicit scope/repair approval, assessment
idempotency, bounded JSON and SSE, resume/dedupe, cancellation and error states
are executable. Full app/browser/M6 acceptance is still Vihaan's unfinished work.

Executed: npm unit test command **13 passed**, strict TS; real-backend command
**4 passed** (parent + 3 subtests), FastAPI over HTTP + exclusive temporary real
PostgreSQL database. Observed cancellation persisted 3 events; resume after 1
returned 2/3; terminal resume returned none and fetched persisted CANCELLED state.
Tests also proved separate-human approval, CSRF denial, tenant 404, idempotency
replay/conflict and active SSE abort. Zero provider calls and target executions.
Node cookie jar is a test helper; browser CORS/SameSite remains unverified.

Found/fixed actual integration details: create-assessment wraps `{assessment,
job_id}`; transport unwraps canonical Assessment and ignores job metadata. A
terminal state_changed precedes terminal notification: consume final event too.
Snapshot endpoint currently deduplicates repo/commit rather than idempotency key.
Adam/Vihaan: wire package tests into frontend CI when scaffold lands; I did not
edit `.github/` or the root frontend package manifest to avoid ownership overlap.

Sai: read PR #31/index-consumer message and acknowledge conservative ambiguous
intent handling. Your consumer test evidence is attributed to your run; attempted
local collection failed (code_review not installed), not independently passing.
Statement/source-span deduplication is recorded as a follow-up, no ID migration
introduced here. Reservation message timestamp was ahead of actual 02:54 UTC
creation; its immutable filename/content were retained and status corrected.
