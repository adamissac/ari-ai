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

Model-proposed CVSS metrics are explicit provisional assumptions, even when they cite an executed run. A run identifier supplies provenance but does not prove an impact. Such scores list every assumption and require human review; missing metrics remain unscored. Incident closure requires actual regression artifact IDs/hashes; eradication requires a succeeded independent Verify run. All currently supported runtime sources are demo/replay/simulation, so correlated incidents retain simulated labeling even for executed demo logs.

Migration revision `0005_incidents` deliberately differs from intelligence-memory PR #39’s `0005`. The runner upgrades all current Alembic heads, allowing independent additive branches to coexist. A real PostgreSQL scratch-database test upgrades both heads, downgrades to base, and upgrades again. Disposable databases from earlier unpublished iterations should be recreated; no production upgrade from an earlier incident prototype is claimed.

Incident eradication recognizes approved security remediation plans only when the plan is persisted on the linked finding and the approval belongs to that assessment/project. Finding-bound reviewer approvals remain supported. Hosted regression source archives now supply the Fortify artifact needed for lessons learned; no hand-made artifact insertion is required.

## Assessment request retries

`POST /projects/{project_id}/assessments` serializes concurrent requests sharing a
user and `Idempotency-Key` within PostgreSQL. An accepted retry returns the same
assessment and job IDs; a changed project or payload returns 409
`IDEMPOTENCY_CONFLICT`. Authorization is checked before a cached response is read,
and failed transactions release the key so an authorized retry can proceed.

The request digest now includes the project URL. Keys cached by earlier versions
use a different digest and return 409 after upgrade; start a new action with a fresh
key. No table, shared model, or response schema migration is required.
