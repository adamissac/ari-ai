# Integration milestones and evidence requirements

- [ ] **M0** shared schemas, importable packages, reproducible local run commands, PR/branch conventions agreed. Gate: 6 owners acknowledge types; CI contract tests pass.
- [x] **M1** intelligence indexes the owned Python example by SHA, structured graphs, expectations and citeable context packs. Gate: tests and provenance inspection.
- [ ] **M2** reviewer with real Claude agent loop can interpret commit intention, call retrieval/tests, generate candidate in safe worktree, inspect results. Gate: live optional smoke and deterministic fixture tests; functional defect reproduced.
- [ ] **M3** 7 *different* agent runners with actual bounded tool-use and distinct permissions and typed handoffs. Gate: observed real model/tool trace per required role (opt-in), fake-provider integration tests; separated Verify actual tests.
- [x] **M4** FastAPI, DB migrations, durable queue, signed idempotent GitHub webhook, scope/approval, persisted audit and SSE. Gate: signed event -> durable queued analysis -> event stream in test.
- [ ] **M5** Double DQN trains from scratch; replay, target/online networks, masks, held-out evaluation and baselines run. Gate: checked env, deterministic seed, checkpoint reload, nonzero learning updates, honest metrics.
- [x] **M6** frontend displays real backend assessments, actual finding provenance, agent steps, approval controls, RL evaluation and monitoring. Gate: browser e2e on live local service; mocks are test-only.
- [x] **M7** unified owned-sandbox demonstration from commit -> index -> review -> seven security agents -> candidate patch -> independent security + functional verify -> regressions -> monitoring event -> dashboard, with errors handled honestly. Gate: automated e2e plus human-inspectable traces.
- [ ] **M8** deployment and continuous live event operations after human approval, safe scope and uptime validation. Gate: independently verified URL, webhook delivery and persistence; no blanket production claims.

For each gate, record exact command, git SHA, environment, pass/fail counts, artifact/PR, and unresolved limitations. Do not mark complete on the basis of screenshots alone.


### M1 producer evidence — Sarosh

PR #6 merged at `bcc2e23`; final head `d608af5` passed both CI test jobs, links and
secret scanning. Focused producer/PostgreSQL/webhook: 24 passed, 1 opt-in skip; broader
suite: 115 passed, 4 skips. Actual target/index evidence and canonical ContextPack fixture
are in code-intelligence/evidence/ and code-intelligence/fixtures/. Index version 0.2.0
includes route-attached ownership intent and two-commit convention invalidation proof.
No full reviewer/seven-agent runtime or live-provider claim is made by this M1 check.


### M6 evidence — Vihaan

Branch `feat/vihaan/frontend` (PR in coordination/status/VIHAAN.md). `cd frontend &&
../.venv/bin/python tests/e2e/stack.py` → Playwright **8 passed** against real FastAPI +
PostgreSQL + worker + `next start`: rendered-UI journey from scope request and
second-member approval through a live SSE timeline, remediation approval, reviewer + seven
agent runs, evidence chain, hash-checked diff and Verify `accepted`, persisting across
reload; monitoring shows a signed GitHub push; offline and contract-violation states are
explicit; Defense Lab plots only the schema-validated bundle. Vitest 23 passed, transport 18
passed, lint/tsc/build clean. Limitation: model replies are TEST-ONLY scripted transports
(`provider_mode=fake`, labelled in the UI); no live-provider run has been rendered yet.


### M4 evidence — Srihith

`uv run pytest -q backend/tests/test_webhook_monitoring.py backend/tests/test_e2e_host.py
backend/tests/test_jobs_queue.py backend/tests/test_api_core.py backend/tests/test_parallel_migrations.py`
→ **34 passed** (macOS arm64, Python 3.12, embedded PostgreSQL 16 via pgserver).
- Covered: an HMAC-signed GitHub push → durable queued analysis (`SKIP LOCKED` leases) → persisted SSE log with `Last-Event-ID` replay. Also scope/approval gates, hash-chained audit verification, and the Alembic single-head check.
- The CI `backend` workflow runs the same suite on every PR touching backend/shared.
- Limitations:
  - no GitHub App credentials, so the installation-token flow is unexercised;
  - Compose/Docker stack not run locally (CI builds the image: `backend-image`).

### M7 evidence — Srihith

`uv run pytest -q backend/tests/test_m7_push_to_regression.py` → **1 passed** (one automated chain).

The chain:
1. a signed push of a real second commit on the owned payments-lite repo;
2. the monitoring event (redelivery is idempotent);
3. reassessment → an assessment pinned to the pushed SHA (trigger `monitoring`);
4. functional review, then all seven security agents;
5. both human approvals through the API;
6. the security patch and the reviewer's functional repair;
7. independent Verify for each (security: re-run check; functional: generated tests fail unpatched and pass patched), each from a distinct verify run;
8. findings end `hardened` / `verified`;
9. verified-regression candidates recorded on the snapshot;
10. the durable event log ends `assessment.completed`, and the audit hash chain verifies.

The dashboard side is covered by the real-stack Playwright journey (`cd frontend && ../.venv/bin/python tests/e2e/stack.py`, 12 passed), which renders the same flow plus the monitoring feed.

Limitations:
- model turns are TEST-ONLY scripted transports (`provider_mode=fake`; the functional Verify makes no model call: `none`), so there is no live-provider M7 run yet;
- the browser journey starts the assessment manually, while the push-triggered chain is asserted at the API level;
- the default monitoring budget (150k tokens / $3) is too small for the full chain. The test raises it to the manual default (400k / $10) through `PATCH /projects/{id}`, as an owner would. Changing the default is a product decision.
