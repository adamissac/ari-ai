# ADR-0026: A commit over the review limit waits; it is not skipped

- Status: accepted
- Date: 2026-11-12

## Context

Per-commit reviews share one hourly and daily pool per project (LAUNCH_DECISION C10). A commit
that arrived with the pool full was recorded as `skipped` and never reviewed. Production had 31
such commits. The product promise is that every commit on a connected repository is reviewed.

## Decision

`assess_github_commit` defers its job until the quota window resets (`JobDeferred`), instead of
recording a skipped request. The pool and the spend cap are unchanged: they now set the pace of
reviews, not which commits get one. Nothing is written for the commit until its review starts,
so the commit list shows it as waiting rather than as a finished skip.

The legacy impact monitor (no per-commit author list) is unchanged and still coalesces.

## Consequences

- A burst larger than the pool takes longer to clear; no commit is dropped for capacity.
- A job waiting on the daily pool can sit queued for up to a day.
- Deferral does not consume retry attempts, so a long wait cannot fail the job.
