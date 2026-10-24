# Execution reliability: lifecycle, recovery, limits and metrics

Status: implemented on `feat/devin-execution-reliability` (migration `0016`).
Extends the PostgreSQL queue of ADR-0005 (`backend/backend/jobs.py`,
`backend/backend/worker.py`); nothing was replaced. Queue semantics stay
**at-least-once**: handlers must still be idempotent.

## Lifecycle

| Requested state            | `jobs.status`        | Meaning |
|----------------------------|----------------------|---------|
| Queued                     | `queued`             | runnable at `run_after` |
| Waiting on a prerequisite  | `waiting` (new)      | `depends_on` job has not succeeded yet |
| Running                    | `running`            | leased by `lease_owner` until `lease_expires_at` |
| Completed                  | `succeeded`          | |
| Failed                     | `failed` / `dead`    | `dead` = retry budget exhausted |
| Cancelled                  | `cancelled`          | |
| Timed out                  | `timed_out` (new)    | `deadline_at` passed (before, during or between attempts) |
| Recovery required          | `recovery_required` (new) | external effect outcome uncertain; operator decides |

Every change goes through `jobs.transition()`, which validates against
`jobs.TRANSITIONS`, applies a compare-and-set on the current status and appends a
row to `job_events` (from/to status, attempt, worker, `ErrorCategory`, reason,
diagnostics). `GET /api/v1/jobs/{id}/history` returns that history. Existing
statuses and the `GET /jobs/{id}` fields are unchanged; new fields are additive.

Structured failure categories (`jobs.ErrorCategory`): `transient`,
`infrastructure` (database), `network`, `backpressure`, `permanent`,
`authorization`, `cancelled`, `deadline_exceeded`, `lease_expired`,
`retry_exhausted`, `prerequisite_failed`, `uncertain_side_effect`, `operator`.
`worker.classify()` maps exceptions to a category and retryability.

## Uncertain external effects

A handler wraps each external side effect in `ctx.effect(key)`. Before the body
runs, `jobs.begin_effect` commits `effect_state='in_flight'` in its own
transaction (refused if the lease, cancellation or deadline no longer allows it).
On normal exit the effect is `settled`.

* Body raises, or the worker dies while the effect is set → the job becomes
  `recovery_required` (from `fail()` or from reconciliation). It is **never**
  re-claimed: the claim query excludes expired leases with an effect set.
* Body raises `EffectNotApplied` → the effect definitely did not happen; normal
  retry rules apply.
* The original worker can still `complete()` a `recovery_required` job (it
  observed the outcome); a different worker cannot.

`live_defense_execute` passes `ctx.effect` into `execute_control`, which guards the
adapter `apply` call. Before this change a worker crash during that call rolled
back the control's `executing` transition and the re-claimed job would call the
adapter again.

Operators resolve with `POST /api/v1/jobs/{id}/recovery`
(`{"resolution": "applied" | "not_applied" | "retry", "note": ...}`), project
**owner** only, audited as `job.recovery_resolved`. `retry` re-queues the job; the
handler re-runs every authorization, mode and cancellation gate it normally runs,
and `retry` is refused once cancellation was requested.

## Recovery (`backend.execution.reconcile`)

Runs at worker start, from `drain()`, and every `WORKER_RECONCILE_INTERVAL_S` in
the worker loop. A transaction-scoped try-lock lets one reconciler run at a time;
rows being mutated by a live worker are skipped (`SKIP LOCKED`). It never runs a
handler. For each expired lease, in order:

1. effect set → `recovery_required` with diagnostics (previous owner, last
   heartbeat, effect key, required action);
2. cancellation requested → `cancelled` (previously such rows stayed `running`
   forever because the claim query skips cancelled rows);
3. deadline passed → `timed_out`;
4. final attempt → `dead`;
5. otherwise → `queued` (next claim increments `attempts`).

It also times out pending jobs past their deadline, promotes/fails `waiting` jobs,
and prunes worker rows not seen for 10 × `WORKER_STALE_S`.

| Failure                         | Handling |
|---------------------------------|----------|
| Worker killed / host restart    | lease expires → reconcile/claim recovers; effect jobs → `recovery_required` |
| Graceful SIGTERM                | unchanged: finish current job, then exit and deregister |
| Orchestrator interruption       | handler exception → classified retry; assessment orchestrator still re-emits by `step_key` |
| DB failure in handler           | `infrastructure`, retried with backoff |
| DB failure finalizing a job     | `complete`/`fail` retried `WORKER_FINALIZE_RETRIES` times; then lease expiry recovers |
| Network failure                 | `network`, retried; inside an effect → `recovery_required` |
| Heartbeat loss                  | handler sees `JobCancelled` on next `check_cancelled()`; `complete` refuses |

## Resource and concurrency limits

* `JOB_MAX_RUNNING_PER_PROJECT` (default 4): live leases per project. Enforced in
  the claim statement; claims serialize on an advisory lock while any limit is on,
  so the limit holds across workers (claims are one short statement).
* `JOB_MAX_RUNNING_GLOBAL` (default 0 = off; the worker count already bounds it).
* Fairness: claim order is `priority`, then the project with the fewest running
  jobs, then age. A project with 1,000 queued jobs cannot starve another project
  at the same priority. Jobs without a project are not limited.
* `JOB_MAX_PENDING_PER_PROJECT` (default 1000): `enqueue` raises
  `QueueBackpressure` (HTTP 429 with `Retry-After`). Dedupe hits and
  `CONTROL_JOB_KINDS` (including emergency stop) are exempt. Soft limit: concurrent
  enqueues can overshoot by the number of concurrent writers.
* Deadlines: `enqueue(..., deadline_s=)` bounds the whole execution. Expired jobs
  are not claimed; heartbeats surface the deadline to the handler
  (`JobDeadlineExceeded`); a retry whose backoff would land past the deadline ends
  `timed_out`.
* Retry budgets: `max_attempts` plus per-kind `RetryPolicy` (exponential, capped,
  positive jitter; default reproduces the original `min(300, 2**n)` curve).
* Resource release: the lease is always released by `complete`/`fail`; the
  heartbeat thread is stopped in `finally`; worker rows are deregistered on exit.

## Observability

No new backend (docs/19): figures are SQL over `jobs`, `job_events` and
`worker_heartbeats`.

* `GET /api/v1/projects/{id}/execution` (project viewer+): status counts, queue
  wait p50/p95/max and oldest pending age, lease ages and expired leases, execution
  duration, retry counts, cancellation outcomes (before start / while running /
  after lease loss / pending), failure categories, recovery required/resolved,
  stuck count by reason, plus the stuck job list.
* `uv run python -m backend.execution stats|stuck|reconcile` (operators): the same
  plus fleet-wide worker counts (active/busy/stale).

Stuck reasons: `recovery_required`, `lease_expired`, `deadline_exceeded`,
`queued_starved` (runnable for > `JOB_STUCK_PENDING_S`), `waiting_on_prerequisite`.

## Runbook

* **`recovery_required`**: read `recovery` on the job (effect key, previous
  owner). Check the external system (for controls: adapter state / control row).
  Resolve `applied`, `not_applied`, or `retry`.
* **`lease_expired` stuck count rising**: workers are dying or overloaded; check
  worker logs and `workers.stale`. Reconcile runs automatically; run it manually
  with `python -m backend.execution reconcile`.
* **`queued_starved`**: per-project limit or worker count too low, or a
  high-priority flood. Compare `leases.running` with `limits`.
* **429 `RATE_LIMITED` from enqueue**: the project has `JOB_MAX_PENDING_PER_PROJECT`
  jobs pending; drain or raise the limit.

## Security boundaries

No new execution capability. Recovery never runs handlers; `retry` goes through the
handler's own gates; OFF-mode cancellation (`modes.cancel_first_responder_jobs`)
and control authorization re-checks are untouched; control jobs are exempt from
backpressure so emergency stop cannot be refused. Project-scoped endpoints use
`require_project`; non-members get 404.

## Limitations

* At-least-once, not exactly-once. Handlers that do external work without
  `ctx.effect` keep the previous replay-on-crash behaviour (they must be idempotent).
* A job whose handler committed its domain write but whose `complete` could not be
  recorded is re-run (or, with an effect set, flagged `recovery_required`).
* Claim serialization is a deliberate trade-off for strict limits at the ADR-0005
  scale (a handful of workers); revisit with the queue interface if that changes.
* `live_defense_agent_step` / first-responder handlers (PR #458 territory) are not
  yet wrapped with `ctx.effect`; see "Integration after PR #458".

## Integration after PR #458

PR #458 owns Scout/Diagnose execution in `live_defense/first_responder.py`. This
work does not edit that file. Once #458 merges, wrap any provider or adapter call it
adds in `ctx.effect("agent:<invocation_id>:<agent>")` and pass `deadline_s` when it
enqueues `live_defense_agent_step`. `FirstResponderInvocation.job_id` already links
invocations to `jobs`, so `/jobs/{id}/history` and the project execution figures
cover them without schema changes.
