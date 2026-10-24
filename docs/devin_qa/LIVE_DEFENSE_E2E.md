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

`test_exec_reliability_compat.py` pins the queue contracts this suite relies
on once `feat/devin-execution-reliability` merges (new `JobStatus` values,
`depends_on`/`deadline_s`/`project_id` on `enqueue`, fair project-limited
`claim`, `begin_effect`/`recovery_required`, `execution.reconcile`). Every
test skips until `jobs.JobStatus.recovery_required` exists.

Scenarios to review at merge time:

- `test_e_worker_failure`: backoff/requeue assertions still hold, but a step
  job that declares an effect lands in `recovery_required` instead of retry.
- `test_j_queue_redelivery`: `revive_job` bypasses the WS1 state machine; the
  compat suite covers real re-claim after lease expiry instead.
- `test_i_concurrent_workers`: claims serialize on an advisory lock when
  per-project limits are on; single-execution semantics hold.

## Coordination notes

- Depends on the unmerged Phase 7C agent-execution stack (PR #458); this branch
  is based on its tip. None of that PR's files are modified here.
- Bugs this suite surfaces in other workstreams get focused issues, not
  in-place fixes.
- `docs/planning/SESSION_HANDOFF.md`, `docs/planning/HACKATL_TASKS.md` and
  `CHANGELOG.md` are intentionally untouched: PR #458 edits them, and the
  workstream instruction is to avoid those files.
