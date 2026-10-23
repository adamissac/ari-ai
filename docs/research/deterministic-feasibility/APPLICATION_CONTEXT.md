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
not performance or production-safety claims. Responses additionally have a
1,024-message cap. Only the existing payment schema is emitted with fresh JSON
headers; downstream cookies, redirects and arbitrary headers are not released.

## Executed verification

Twenty integration tests pass against the actual payments-lite application:

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
- Bind the returned payment ID and owner to the authorized request using the
  existing PaymentOut schema. Reject malformed/duplicate JSON, extra fields,
  invalid framing, error payloads and contradictory customer records. Preserve
  valid chunked responses, strip downstream headers and recheck freshness after
  response validation.

These are integration regressions, not a rerun of the preregistered comparison or
new population evidence. Original timing compliance remains uncertifiable; the
complete feasibility gate remains inconclusive. No training, holdout replay, model
promotion, production deployment or customer enforcement is authorized here.

Next: independently review this private-store/serialization assumption before any
application adapter proposal. A real system needs canonical authorization facts,
transactional consistency and permissions from its own authorization service;
this in-memory fixture cannot establish those properties or justify RL training.

## RL-CMDP-004: response identity integrity

Manual review reproduced a concrete gap in the original wrapper: with an injected
wrong downstream response, an authorized request for Alice's pay_a1 returned
Bob's pay_b1 with HTTP 200. The wrapper now requires a complete successful response,
validates the existing example PaymentOut schema, and checks both payment and owner
against the captured authorization context before emitting a newly serialized body.
Duplicate JSON keys and unexpected fields are rejected rather than reinterpreted.

This binds declared response identity and shape. It does not prove the provenance
of arbitrary financial fields if a downstream implementation forges matching IDs.
All original private-store/single-worker assumptions and the prior timing-evidence
limitation remain. No original comparison was rerun or modified.
