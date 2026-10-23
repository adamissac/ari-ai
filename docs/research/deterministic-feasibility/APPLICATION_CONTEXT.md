# Owned payments-lite application-context integration

RL-CMDP-003, owner-authorized continuation after PR #394. This is an opt-in
research wrapper around the actual deliberately vulnerable payments-lite app;
it has no serving registration, public API, network listener or RL action.
The example source and both prior comparison artifacts remain unchanged.

## Trust and request binding

`PaymentReadLab` owns a deep-copied fixture store. Bearer tokens resolve through
that store, payment IDs come from the canonical GET route, ownership comes from
the current stored payment, and grants come only from trusted Python fixture
mutation methods. HTTP principal/owner/grant headers and query parameters cannot
supply authority. Duplicate authorization headers, missing facts and ambiguous
encoded routes do not forward. The wrapper exposes only payment reads; HTTP
writes and other routes are rejected. It is not a general payments API gateway.

The existing internal ReadContext/ReadGrant and pure guard are reused. No new
canonical shared model or operational control lifecycle is introduced. Parallel
PR #393 continues to own that separate integration.

## Concurrency and freshness semantics

One asyncio lock spans context capture, downstream application execution, buffered
response checks and release. Trusted token/ownership/grant updates share this lock.
Revocation is linearized when its update completes; it does not retroactively
cancel an earlier read. Every later request sees the updated grants. Store mutation
outside these methods is unsupported: this single-process fixture is not a design
for multiple application workers or external database writers.

Contexts expire after five integer fixture ticks. Both context freshness and grant
validity are rechecked before releasing any buffered response. A clock rollback,
expiry or unknown context returns explicit abstention (503). Downstream execution
has a five-second timeout and a 64 KiB buffered-body limit. These are fixture bounds,
not performance or production-safety claims.

## Executed verification

Eight integration tests pass against the actual payments-lite application:

- Reproduce the original unauthorized HTTP 200, then reject it under the wrapper;
  preserve owner and exact-resource delegated reads and the second principal's
  own reads. A neighboring resource remains denied.
- Observe grant expiry/revocation, unknown grants, token rotation/revocation and
  ownership transfer immediately on subsequent requests; reject duplicate auth
  headers and request-supplied context spoofing.
- Force a response/update race for grant expiry, context expiry and clock rollback.
  Buffering releases no payment body on abstention. Revocation waits for the read,
  completes, then blocks the next request.
- Unknown or contradictory store facts never forward; a downstream timeout or
  oversized body releases no data and leaves permission updates usable.

These are integration regressions, not a rerun of the preregistered comparison or
new population evidence. Original timing compliance remains uncertifiable; the
complete feasibility gate remains inconclusive. No training, holdout replay, model
promotion, production deployment or customer enforcement is authorized here.

Next: independently review this private-store/serialization assumption before any
application adapter proposal. A real system needs canonical authorization facts,
transactional consistency and permissions from its own authorization service;
this in-memory fixture cannot establish those properties or justify RL training.
