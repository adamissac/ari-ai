# Srihith — implementation status

Owner: Srihith
Branch: `feat/srihith/backend-monitoring`
Current task: integration host for all pillars. PayloadStore (Sarosh), runtime ingest and the seven-agent hosting adapter (Alan) are done. Next: single intelligence layer (Sarosh intel behind Alan's CodeIntel port), and reviewer/frontend when their branches land.
Last remote sync: 2026-10-17 ~02:30Z (main 369a9a0)
API/contract dependencies: Alan `security_agents.api:build_orchestrator`; Sarosh `code_intelligence.api:build_service` (+ persistence port); Sai `code_review.api.review`; Adam `rl_defense` (integrated)
Verified tests: see session log (exact command + counts)
Recent PR/commit: merged #8, #14, #16, #20, #24, #25; issues #9, #17
Blockers: none hard. The GitHub App flow is unexercised because no App credentials are configured. Docker is not installed, so the Compose file is unverified.
Next action: ack/counter from owners on V0 contracts; Postgres persistence port for Sarosh; wire Alan's orchestrator when `security_agents.api` exists; live LLM smoke once a key is authorized.

## Session entries

Add dated factual entries; do not overwrite history. Never claim unexecuted tests passed.

### 2026-10-17 (session 1)
- Commits on `feat/srihith/backend-monitoring`:
  - `7c7fe0a` shared V0 contracts + codegen + fixtures
  - `63859bf` backend + monitoring
  - `95f1b81` merge of origin/main
  - `b60988c` RL integration
  - `3c52f60` infra/docs
  - plus this coordination commit
- Implemented:
  - strict `shared/` V0 with JSON Schema and TypeScript generation;
  - PostgreSQL schema and Alembic migration, with the audit log append-only via a DB trigger;
  - durable job queue and worker;
  - FastAPI `/api/v1`: sessions, CSRF, org authz, projects, repos, scopes, approvals, assessments with idempotency, findings, patches, artifacts, monitoring, RL, audit, and SSE with `Last-Event-ID`;
  - signed GitHub webhook with dedupe;
  - monitoring normalize → correlate → policy;
  - `AssessmentHost` gates;
  - Claude gateway (Anthropic SDK, `claude-opus-5-5`, FakeTransport for CI);
  - RL recommendation job using Adam's `platform_mapping`;
  - Makefile, Compose and Dockerfile, plus a signed-webhook replay tool.
- Executed tests (macOS arm64, Python 3.12.13, PostgreSQL 16.2 via pgserver, tsc 5.6.3, rl_defense from `origin/feat/adam/rl-defense` + torch 2.14.1 installed locally):
  - Command: `TSC=… .venv/bin/python -m pytest -q` → **83 passed, 1 skipped** (skip = opt-in live LLM smoke).
  - Without TSC and rl_defense, `uv run pytest -q` → 81 passed, 2 skipped (earlier run, same code minus the new monitoring test).
- Live local smoke (real HTTP, separate API and worker processes):
  - signed push → 202 → monitoring event `processed` → reassessment `started` → monitoring assessment;
  - the assessment ends `FAILED / SUBSYSTEM_UNAVAILABLE` because `security_agents` isn't installed (correct, honest outcome);
  - SSE events: state_changed ×3 + assessment.failed.
- NOT verified:
  - real Anthropic call (no key);
  - real GitHub App / OAuth exchange (no credentials);
  - `docker compose up` (Docker not installed);
  - 24/7 operation (nothing deployed).
- Messages:
  - `20261017T010331Z-srihith-to-all-contracts-v0`
  - `20261017T010332Z-srihith-to-adam-rl-contract-accepted`
  - `20261017T010333Z-srihith-to-sarosh-persistence-port`
- Later in session 1:
  - `e6af6e9`: mypy is now clean on shared and monitoring and runs in CI. Malformed nested webhook fields no longer crash the worker.
  - Added `.github/workflows/backend.yml`: ruff, mypy, contract freshness, and pytest against a Postgres service plus tsc.
  - First CI run on PR #8 failed on `ruff format --check` for `backend/replay_webhook.py`. That is fixed in `e6af6e9`.
  - Local result: `84 passed, 1 skipped`.

### 2026-10-17 (session 1, continued)
- **Tier 3 live smoke executed once:** `make smoke-live` → 1 passed.
  - Model `claude-opus-5-5`, 2 turns.
  - Tool calls `read_file` → `submit_result`.
  - Usage: 1,375 input and 178 output tokens; cost $0.00906.
  - The key lives in a local git-ignored `.env` (chmod 600) per issue #10.
- Fixes:
  - live-key capture in the test conftest (`323fd9c`);
  - settings treat empty or `replace-me` values as unset (`9c57a24`).
- Contracts 0.2.0: `RLExplanation` and `FeatureContribution`, migration 0002, endpoint `GET /defense-recommendations/{id}/explanation` (`14e65a2`).
- Merged `origin/main` twice: Adam's #1 RL, #5 payments-lite and #7 CI.
- Tests: `.venv/bin/python -m pytest -q` → 85 passed, 1 skipped (with `rl-defense` + tsc).

### 2026-10-17 (session 1, later)
- PR #14 (merged):
  - `backend.intel_store.PostgresPayloadStore` for Sarosh's PayloadStore, plus migration 0003.
  - Integration-tested: Sarosh's IntelligenceService indexes two real payments-lite commits through it, and a signed push yields **symbol-level** impact.
  - `load_factory` now degrades when a subsystem factory fails to initialize.
- PR #16 (merged): runtime signal ingestion, contracts 0.3.0.
  - Hashed per-project ingest tokens and `/ingest/runtime/{project_id}`.
  - Explainable per-route scoring and labeled `log_anomaly` events.
  - Signals feed rl_defense `RouteSignal`. Migration 0004.
- PR #20 (merged): `backend.adapters.security_agents` hosts Alan's unmodified Orchestrator in the worker, with live mirroring into AssessmentHost and real API approval. Contracts 0.4.0 (id bodies allow `_` and `-`).
  - E2E test with Alan's FakeLLM scripts: 7 agents → COMPLETED, finding verified→hardened, Verify attributed to its own run, diff artifact, 13 SSE states.
- Test infra fix: conftest reuses one embedded server and drops its database per session. 34 leaked servers had exhausted macOS shared memory; I stopped them and cleaned their segments.
- Evidence:
  - local `pytest -q` → 103 passed, 1 skipped (security_agents @ c417b77, code-intelligence, rl-defense installed);
  - CI backend green on each PR (cross-owner tests skip in CI because those packages aren't installed).
- Open asks:
  - Alan (#17): rebase, resolve the payments-lite layout, adopt `shared`, add hooks.
  - Sarosh: a `build_service()` factory option for the Postgres store, and relaxing the `pathspec` pin.

### 2026-10-17 (session 1, latest)
- #24 (merged):
  - Contracts 0.5.0 add the early REPORTING edges (Alan's state table); docs/08 updated.
  - The worker keeps one orchestrator per process.
  - Unknown run id now gives `NOT_FOUND`.
  - Adapter snapshots honor `target_dir`, pinned to git.
  - `test_security_agents_host_mode.py` is an xfail acceptance test for Alan's host mode against the real backend; 5 issues were reported to him.
- #25 (merged): the hosted assessment now runs Sai's reviewer at FUNCTIONAL_REVIEW.
  - `test_unified_assessment.py`: one assessment gives reviewer + 7 security agents, functional and security findings, approval, COMPLETED. Model turns are scripted and labeled fake.
- Verified Sai's code-review suite against the real main backend: 33 passed, 1 skipped. I corrected an earlier message whose run had used his branch's backend copy.
- Evidence:
  - local `pytest -q` → 105 passed, 1 skipped, 1 xfailed (all optional packages installed);
  - CI backend → 98 passed, 5 skipped (code-intelligence is now in the workspace, so its integration tests run in CI).
- Open:
  - Alan's host-mode fixes (#17).
  - A canonical CheckCategory list (awaiting Alan's ack).
  - Vihaan's frontend: no branch yet.
  - Docker Compose and the GitHub App are still unverified (no Docker or App credentials here).
  - A live (paid) end-to-end run of the hosted pipeline hasn't been done; only the gateway smoke test was live.

### 2026-10-17: first LIVE unified assessment (one run, budget $5)
- Run: `asm_01M53VKYE48N4EWWW83P2HNJ5P`, payments-lite @ `4cdea2f`.
- Result: COMPLETED in 53 s. Cost **$0.3696**: 6 LLM calls, 63,854 input and 5,709 output tokens.
- Reviewer (Sai, live): 2 validated functional findings (refund bound, payment IDOR). Both are planted defects.
- Scout (Alan, live): failed with Anthropic 400 `For 'integer' type, property 'minimum' is not supported` (req_011Cg731RCPhRHAuYot4htpd). No other security agents ran. Reported to Alan; I'll re-run after his fix.

### 2026-10-17: fixing blockers in teammates' code (user-authorized while Alan is away), PR #36 merged
- Root cause: security-agents tool schemas were invalid for the Anthropic API, so all 7 agents failed live. Fixed (`strict_schema.py`), verified 7/7 via `count_tokens`.
- Failed Scout now FAILS the assessment.
- Host mode fixed (5 issues) and made the single hosting path: git-pinned checkout via the bindings registry, no implicit labels.yaml, reviewer at FUNCTIONAL_REVIEW, Docker by default. My backend adapter was removed.
- security-agents joined the workspace and CI.
- Results: root suite 148 passed; security-agents 344 passed; CI green across 6 workflows.
- Not yet re-verified live end to end after the fixes (needs one more paid run).

### 2026-10-17: standards integration follow-up
- Branch `feat/srihith/standards-alignment` builds on Alan PR #49 canonical work; shared0.7, persisted incident API, reports and producers, OWASP2025/2026 self-assessment, typed transport.
- Evidence: root193 passed/2 live skips, security/reviewer400 passed/11 optional skips, RL82 passed, transport16 unit+4 real API tests, generated freshness and link check233/0.
- Not claimed: production standards compliance, customer LLM-risk scanning, mounted frontend pages, paid live rerun, deployed containment.

### 2026-10-17: #49 landed via #57; RL expectations; recipe templates
- PR #57 is merged (`22c8c36`): Alan's standards work is on main.
  - Migration 0006 is the single head.
  - Reviewer CWE adjudication is non-fatal (Sai blocker 1).
  - Transport fixture includes `Finding.standards`.
  - CI: 11/11 green.
- `feat/srihith/rl-expectations`:
  - `platform_facts` now feeds persisted expectations to RL (closing Adam's gap).
  - The recipe uses real route templates, and the check library binds named path params.
  - Tests: real-index RL test 2 passed (locally, with `rl_defense`); security-agents 351 passed; root 308 passed.
- Open: CI never runs the RL tests because `rl_defense` is not a workspace member (torch). Sai's span-verifier tolerance is still his.
