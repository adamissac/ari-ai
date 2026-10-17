# backend/

The control plane: the FastAPI `/api/v1` API, PostgreSQL persistence and migrations, the
durable job queue and worker, the hash-chained audit log, the artifact store, GitHub
webhook and App integration, the Claude LLM gateway, and the `AssessmentHost` that runtime
agents use. Owner: **Srihith**. Spec: [docs/13](../docs/13_BACKEND_API_DESIGN.md),
[docs/10](../docs/10_CONTINUOUS_MONITORING.md). Integration guide for the other owners:
[INTEGRATION.md](INTEGRATION.md).

## What exists (verified by tests on this branch)

| Area | Module | Status |
|---|---|---|
| Settings from env | `settings.py` | implemented |
| Schema + Alembic migration (append-only audit trigger) | `db.py`, `migrations/` | implemented; up/down/up tested |
| Durable queue: SKIP LOCKED, leases, heartbeats, retry/backoff, dead-letter, cancel | `jobs.py`, `worker.py` | implemented; crash/lease-expiry recovery tested |
| Sessions (dev login + GitHub OAuth), CSRF, org authz, rate limits, idempotency | `api/` | implemented; OAuth exchange not exercised against real GitHub |
| Projects, repos, scopes (approver ≠ requester), approvals, assessments, findings, patches, artifacts, audit | `api/routes.py` | implemented |
| SSE with `Last-Event-ID` resume from the durable log | `api/routes.py` | implemented |
| GitHub webhook: size bound, HMAC on raw body, delivery dedupe, redacted payload, enqueue | `api/webhooks.py` | implemented |
| Monitoring pipeline (normalize → correlate → policy → reassessment) | `pipeline.py` + `monitoring/` | implemented; symbol-level impact waits on code-intelligence |
| AssessmentHost gates (transitions, scope, approval, budget, cancel, Verify independence) | `host.py` | implemented |
| Claude gateway (Anthropic SDK, retries, typed errors, usage/USD, redaction, tool loop) | `llm.py` | implemented; live provider exercised once via `make smoke-live` (claude-opus-5-5, 2 turns, $0.009) |
| RL recommendations + explanations via `rl_defense` | `pipeline.py` | integrated and tested against `rl-defense` on main |
| GitHub App installation tokens / compare API | `github.py` | implemented; **not exercised against a real App** |
| Seven-agent orchestrator | — | **not here**: Alan's `security_agents`. Until it lands, assessments end `FAILED / SUBSYSTEM_UNAVAILABLE` |
| Runtime signal ingestion: per-project ingest tokens, `/ingest/runtime/{project_id}`, explainable per-route scoring, labeled `log_anomaly` events, RL signal feed | `api/runtime.py` + `monitoring/runtime.py` | implemented; inputs are demo/replay/simulated only (no production telemetry) |
| Code-intelligence PayloadStore (Postgres) | `intel_store.py` | implemented; integration-tested with Sarosh's IntelligenceService |
| `POST /patches/{id}/pull-request`, `PATCH /expectations/{id}` | — | **not implemented** (MVP cut order / owned by intelligence) |

## Commands

```bash
uv sync                                  # install workspace (Python 3.12)
make test                                # all tests; embedded real PostgreSQL if DATABASE_URL unset
make check                               # ruff + generated-contract freshness
make dev                                 # migrate + API (:8000) + worker against embedded Postgres
docker compose up --build                # alternative: Postgres + migrate + API + worker
uv run python -m backend.replay_webhook --repo owner/name --head <sha> --path app/x.py   # signed local delivery
RUN_LIVE_LLM_EVAL=1 ANTHROPIC_API_KEY=... make smoke-live   # opt-in real Claude call (costs money)
```

Set `TSC=/path/to/tsc` to run the generated-TypeScript compile test.
`TEST_DATABASE_URL` points tests at an existing server. Each run creates a fresh database.

## Rules this package enforces

* No long or LLM work in request handlers. The API enqueues and the worker executes.
* No endpoint executes commands, accepts code to run, merges, or deploys.
* Every state change is authorized in code and appended to the audit chain.
* A missing subsystem, key, checkpoint or GitHub App is reported as an explicit error
  code, never replaced with fabricated output.

## Standards and incidents

Migration 0005 adds persisted incidents. Owner-authenticated incident create/actions use the shared contracts and canonical `standards.incident` rules, with database checks for project links, approval, independent Verify, and regression artifacts. Runtime anomalies correlated with validated findings create reports for human triage, not confirmed incidents. See [incident handling](../docs/security/NIST_INCIDENT_HANDLING.md). Reports include persisted classifications and hardening records. `AssessmentHost.record_standards` updates classifications without reverting finding status/history. Incident SSE provides finite durable replay, not a continuously held connection.
