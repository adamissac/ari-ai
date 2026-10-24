# Live Defense end-to-end suite (Workstream 2)

Owner: Alan Mozhoor. Branch: `feat/devin-live-defense-e2e`.

Automated owned-staging integration tests for the first-responder pipeline,
in `backend/tests/live_defense_e2e/` (runbook: that directory's `README.md`).
Scenarios A–H run on real HTTP routes, real PostgreSQL, the real durable job
queue and the real `security_agents` runtime; the model is scripted
(`provider_mode="fake"` everywhere). FakeLLM results do not validate real
Anthropic execution — the only live test is opt-in (`live_llm`).

## Commands

| Tier | Command | Runs in CI |
|---|---|---|
| Fast smoke | `make e2e-ld-smoke` | yes (PR) |
| Full integration (A–R) | `make e2e-ld` | yes (PR) |
| Failure injection (D–F, J–L, N, R) | `make e2e-ld-fault` | yes (PR) |
| Live provider (opt-in, costs money) | `make e2e-ld-live` | manual only |

CI: `.github/workflows/live-defense-e2e.yml`. Machine-readable results land in
`test-results/live-defense-e2e/` (git-ignored; uploaded as CI artifacts).

## Scenario map (second round)

- I — concurrent workers: two `worker.drain` threads claim each step exactly
  once; no double execution.
- J — queue redelivery after a persisted result: a re-claimed finished step
  job is an idempotent no-op (no second model call, no second transcript).
- K — provider failure after partial model output: truncated turn + provider
  death fails honestly (`LLM_UNAVAILABLE`) with the partial turn retained.
- L — OFF during an active provider call (first Diagnose turn).
- M — stale deployment mapping: a window that predates the only trusted
  mapping is UNKNOWN-correlated; no agent reads code.
- N — artifact corruption / missing bytes: the store refuses both (sha256
  integrity error / FileNotFoundError) and recovers.
- O — cross-project artifact access: another tenant gets 404 on
  `GET /artifacts/{id}`.
- P — duplicate telemetry ingestion: replayed window is deduped (no new
  window, event, job or decision; exactly one run per agent).
- Q — invalid authorization scope: an expired scope is no scope —
  `skipped_no_scope` while read-only agents still run.
- R — OFF suppresses dispatch: an anomalous window while OFF produces no
  executed agent work (no new decision, or only cancelled ones; zero model
  calls).

## Workstream 1 (execution reliability) compatibility

`test_exec_reliability_compat.py` runs **live against the reliability queue**
— this branch is rebased on the composition of the approved heads
`89a3deba` (PR #458, Phase 7C) + `17c3ded0` (execution reliability), so the
contract tests execute for real, never skipped. They pin
`depends_on`/`deadline_s`/`project_id` on `enqueue`, fair project-limited
`claim`, `begin_effect`/`recovery_required`, `execution.reconcile`, and
deadline timestamps expressed on the **database clock**
(`sa.func.now() - interval`), never Python `utcnow()` — review finding F10.

Three tests carry `xfail(strict=True)`: each reproduces a review-confirmed
integration defect (F1, F7, F8) against the desired contract, so CI stays
green while the defect stays visible; when the owning workstream lands the
fix the test turns XPASS and the marker is dropped.

- **F1** — crash-after-send/before-response: reconcile requeues the
  uncertain attempt and a worker replays the billable provider call
  automatically. Required: `recovery_required`, no second physical call
  until an operator resolves it.
- **F7** — `live_defense_agent_step` jobs are enqueued with
  `deadline_at=NULL` (no durable deadline).
- **F8** — OFF flipped while the final submit response is in flight is
  overwritten: the cancelled invocation is persisted as `executed`.

Passing coverage on the same file: dependency ordering, per-project claim
fairness, deadline `timed_out` on the DB clock, uncertain effect →
`recovery_required`, and deadline durability through claim → lease expiry →
reconcile → requeue (the stored `deadline_at` is never reset).

Physical vs logical accounting: `fake.calls` counts physical provider calls;
invocation rows count logical attempts. `test_e_worker_failure` asserts the
honest observed contract — a re-delivered step re-runs the whole physical
loop (scout calls double) even though the logical invocation stays one — and
does not claim that as duplicate-prevention.

## Coordination notes

- Depends on the unmerged Phase 7C agent-execution stack (PR #458); this branch
  is based on its tip. None of that PR's files are modified here.
- Bugs this suite surfaces in other workstreams get focused issues, not
  in-place fixes.
- `docs/planning/SESSION_HANDOFF.md`, `docs/planning/HACKATL_TASKS.md` and
  `CHANGELOG.md` are intentionally untouched: PR #458 edits them, and the
  workstream instruction is to avoid those files.
