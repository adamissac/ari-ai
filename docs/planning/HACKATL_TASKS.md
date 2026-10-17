# HackATL task board

Status values: [planning/README](README.md#task-status-values). **All owners are
UNASSIGNED** until the team agrees roles ([TEAM_ASSIGNMENTS](TEAM_ASSIGNMENTS.md)).
`READY` tasks still require Phase 1 authorization ([MASTER_ROADMAP](MASTER_ROADMAP.md)).
Dependency graph: [DEPENDENCIES](DEPENDENCIES.md). Post-MVP: [BACKLOG](BACKLOG.md).

Rules: edit only your own rows; set owner + `IN_PROGRESS` + branch when you start;
acceptance criteria are the minimum for `DONE` in addition to
[DEFINITION_OF_DONE](DEFINITION_OF_DONE.md).

## Phase 0 — Repository & architecture

| ID | Title | Dir | Reqs | Depends on | Owner | Status | Acceptance criteria |
|---|---|---|---|---|---|---|---|
| DOCS-001 | Phase 0 docs, contracts-as-docs, planning, skeleton READMEs | docs/, */README.md | — | — | UNASSIGNED | DONE | All linked docs exist; links resolve; no application code |
| INFRA-001 | Create private GitHub repo and push Phase 0 | — | — | DOCS-001 | UNASSIGNED | DONE | Private repo `adamissac/hackatl-agentic-security` exists with `main` pushed |

## Phase 1 — Foundations & walking skeleton

| ID | Title | Dir | Reqs | Depends on | Owner | Status | Acceptance criteria |
|---|---|---|---|---|---|---|---|
| DOCS-002 | Ratify or amend proposed ADRs 0001–0010 | docs/decisions | — | — | UNASSIGNED | READY | Each ADR Accepted/Rejected/Superseded with date and deciders |
| DOCS-003 | License decision | LICENSE, LICENSE-DECISION.md | — | — | UNASSIGNED | DONE | Interim proprietary LICENSE added; long-term choice revisited before going public |
| DOCS-004 | Set Code of Conduct maintainer contact | CODE_OF_CONDUCT.md | — | — | UNASSIGNED | READY | Contact channel listed |
| INFRA-002 | Enable private vulnerability reporting + branch protection on `main` | GitHub settings | — | INFRA-001 | UNASSIGNED | READY | Settings enabled; SECURITY.md note updated |
| INFRA-003 | `docs.yml` (link + Mermaid check) and `secrets.yml` (gitleaks) workflows | .github/workflows | NFR-08 | INFRA-001 | Adam | IN_REVIEW | Workflows green on `main`; actions pinned by SHA; least-privilege permissions |
| INFRA-004 | Docker Compose dev stack (postgres, api, worker, frontend) | repo root, scripts/ | NFR-09 | CORE-002, UI-001 | UNASSIGNED | BLOCKED | `docker compose up` gives healthy api + frontend; documented in CLAUDE.md Commands |
| INFRA-005 | Pinned sandbox base images (`test-runner`, `check-runner`) | scripts/, security-agents/ | NFR-01 | — | UNASSIGNED | READY | Images build reproducibly; pinned digests; non-root user |
| CORE-001 | `shared/` package with core Pydantic models from doc 12 | shared/ | all | — | UNASSIGNED | READY | Models for tenancy, scope, snapshot, finding, evidence, assessment; `extra="forbid"`; round-trip tests |
| CORE-002 | Backend FastAPI skeleton, Settings, `/healthz` `/readyz`, ruff/mypy/pytest, `backend.yml` | backend/ | FR-P-* | CORE-001 | UNASSIGNED | BLOCKED | App starts; health endpoints tested; CI job green |
| CORE-003 | Contract codegen: Pydantic → JSON Schema → TS; `contracts.yml` | shared/, scripts/ | — | CORE-001 | UNASSIGNED | BLOCKED | `scripts/` command regenerates; CI fails on dirty diff |
| CORE-004 | PostgreSQL schema, Alembic migrations, org/project-scoped repository layer | backend/ | FR-P-02 | CORE-002 | UNASSIGNED | BLOCKED | Migrations up/down tested; repository layer requires org/project ids |
| CORE-005 | GitHub OAuth sign-in + projects/repositories API | backend/ | FR-P-01, FR-P-02 | CORE-004 | UNASSIGNED | BLOCKED | OAuth flow works locally; endpoints per doc 13 with tests |
| CORE-006 | Postgres job queue (`SKIP LOCKED`), worker runner, leases, SSE stream | backend/ | — | CORE-004 | UNASSIGNED | BLOCKED | Jobs leased/requeued on expiry; SSE emits test events; tests |
| CORE-007 | AuthorizedScope + approvals API wired to `scope_guard` | backend/ | FR-P-03 | CORE-004, SEC-002 | UNASSIGNED | BLOCKED | Scope lifecycle endpoints; approver ≠ requester rule; SB-02 passes |
| CORE-008 | Hash-chained append-only audit log | backend/ | FR-P-04 | CORE-004 | UNASSIGNED | BLOCKED | Chain verification test; DB role cannot update/delete |
| CORE-009 | Artifact store abstraction (local FS, SHA-256 addressing) | backend/ | — | CORE-001 | UNASSIGNED | BLOCKED | Put/get with hash verification; path traversal tests |
| CORE-010 | LLM gateway: Claude client, budgets, redaction, schema validation, record/replay | backend/ | FR-P-05, NFR-04, NFR-07 | CORE-001, CORE-009 | UNASSIGNED | BLOCKED | Budget pre-check + reconciliation; invalid output → `SCHEMA_INVALID`; replay mode; SB-11 passes |
| SEC-001 | AgentSpec runtime: agent loop, tool calls, output validation, step budgets, recording | security-agents/ | NFR-04 | CORE-010 | UNASSIGNED | BLOCKED | FakeLLM-driven tests for success, invalid output retry, budget stop |
| SEC-002 | Tool registry + `scope_guard` (pure) | security-agents/ | NFR-02 | CORE-001 | UNASSIGNED | BLOCKED | Allowlist enforcement (SB-06); scope_guard exhaustive tests ≥ 95% branch |
| SEC-003 | Sandbox driver: profiles, network `none`, limits, reaper | security-agents/ | NFR-01, NFR-02 | INFRA-005 | UNASSIGNED | BLOCKED | SB-03, SB-05 pass; orphan reaping tested |
| UI-001 | Next.js scaffold, Tailwind, ESLint/tsc, generated API client, `frontend.yml` | frontend/ | — | CORE-003 | UNASSIGNED | BLOCKED | Builds; typed client generated; CI green |
| DEMO-001 | `examples/payments-lite` vulnerable demo target with fixtures + build recipe | examples/ | — | — | Adam | IN_REVIEW | Documented planted functional bug + authorization weakness; passing (incomplete) test suite; builds in sandbox |
| TEST-001 | Test harness: FakeLLM, recorded-response replay, fixture layout | tests/ | — | CORE-010 | UNASSIGNED | BLOCKED | Replay of a recorded fixture through gateway in tests |
| TEST-002 | Contract test suite (IC-1) | tests/contract | — | CORE-003 | UNASSIGNED | BLOCKED | Round-trip + schema drift + OpenAPI checks green |

## Phase 2 — Understand & review (P1)

| ID | Title | Dir | Reqs | Depends on | Owner | Status | Acceptance criteria |
|---|---|---|---|---|---|---|---|
| INTEL-001 | Repo ingestion at SHA into worker workspace | code-intelligence/ | FR-1-01 | CORE-001 | Sarosh | DONE | Clone at SHA (GitHub App or local path); tree hash recorded; no execution |
| INTEL-002 | Tree-sitter parsing infra + file classification | code-intelligence/ | FR-1-01 | INTEL-001 | Sarosh | DONE | Parses Python fixtures; classifies test/vendored/generated |
| INTEL-003 | Python symbol extractor | code-intelligence/ | FR-1-02 | INTEL-002 | Sarosh | DONE | Golden tests for modules/classes/functions/methods, spans, decorators, docstrings |
| INTEL-004 | Python import + call graph with resolution confidence | code-intelligence/ | FR-1-02 | INTEL-003 | Sarosh | DONE | Golden edges on fixtures; `exact/likely/unresolved` labeled |
| INTEL-005 | FastAPI/Flask entry-point adapters incl. auth dependencies | code-intelligence/ | FR-1-02 | INTEL-003 | Sarosh | DONE | All payments-lite routes detected with auth deps |
| INTEL-006 | Behavioral expectation extractors + LLM inference with citation validation | code-intelligence/ | FR-1-03 | INTEL-004, INTEL-005, CORE-010 | Sarosh | DONE | payments-lite yields ownership + refund-bound expectations with provenance (IC-3) |
| INTEL-007 | Context pack retrieval (graph + BM25, budgeted, delimited) | code-intelligence/ | — | INTEL-004, INTEL-006 | Sarosh | DONE | Packs within budget; provenance per chunk; untrusted delimiters |
| INTEL-008 | Incremental indexing + `affected_by_diff` | code-intelligence/ | FR-1-09, FR-3-02 | INTEL-004 | Sarosh | DONE | ImpactSet correct on fixture diffs |
| REVIEW-001 | Expectation-vs-implementation review with structured verdicts | code-review/ | FR-1-05 | INTEL-007, CORE-010 | UNASSIGNED | BLOCKED | Verdicts schema-valid with cited spans; recorded-response tests |
| REVIEW-002 | Behavioral test generation + sandboxed execution | code-review/ | FR-1-06 | REVIEW-001, SEC-003 | UNASSIGNED | BLOCKED | Refund-bound bug validated by failing generated test |
| REVIEW-003 | Candidate repair in isolated worktree | code-review/ | FR-1-07 | REVIEW-002 | UNASSIGNED | BLOCKED | Repair produces PatchCandidate accepted by Verify (IC-5, needs SEC-010) |

## Phase 3 — Security team (P2)

| ID | Title | Dir | Reqs | Depends on | Owner | Status | Acceptance criteria |
|---|---|---|---|---|---|---|---|
| SEC-004 | Probe sandbox runner: target builder, check-runner, target-only network | security-agents/ | FR-2-02, NFR-02 | SEC-002, SEC-003, DEMO-001 | UNASSIGNED | BLOCKED | SB-01, SB-04 pass; payments-lite target reachable only from check-runner |
| SEC-005 | Check template library v0 (`access_control.ownership`, `input_validation.bounds`), read-only | security-agents/ | FR-2-02 | SEC-004 | UNASSIGNED | BLOCKED | Templates reviewed by security owner; deterministic `matches_expectation` |
| SEC-006 | Scout agent | security-agents/ | FR-2-01 | SEC-001, INTEL-007 | UNASSIGNED | BLOCKED | Raises planted authz hypothesis on payments-lite with valid citations |
| SEC-007 | Probe agent | security-agents/ | FR-2-02 | SEC-001, SEC-005 | UNASSIGNED | BLOCKED | Confirms planted, refutes non-planted fixture hypothesis |
| SEC-008 | Trace agent + deterministic severity function | security-agents/ | FR-2-03 | SEC-001 | UNASSIGNED | BLOCKED | All steps labeled; severity factors cited |
| SEC-009 | Diagnose agent | security-agents/ | FR-2-04 | SEC-001 | UNASSIGNED | BLOCKED | Root cause span matches fixture label |
| SEC-010 | Verify agent + deterministic verdict rules | security-agents/ | FR-2-06 | SEC-001, SEC-003, SEC-004 | UNASSIGNED | BLOCKED | SB-08, SB-09 pass; detects planted bad patches |
| SEC-011 | Patch agent (worktree) | security-agents/ | FR-2-05 | SEC-001, SEC-003 | UNASSIGNED | BLOCKED | Produces diff within plan scope; local tests run |
| SEC-012 | Orchestrator state machine + gates (IC-2 with fake agents) | security-agents/, backend/ | FR-P-05 | CORE-006, CORE-007, SEC-001 | UNASSIGNED | BLOCKED | All transitions tested incl. cancel/fail/budget; SB-07 passes |
| SEC-013 | Fortify agent + regression test promotion | security-agents/ | FR-2-07 | SEC-001 | UNASSIGNED | BLOCKED | Every verified finding gets ≥ 1 RegressionTest |
| TEST-003 | Security-boundary suite SB-01…SB-12 | tests/security | NFR-01, NFR-02 | SEC-003, SEC-004, CORE-007 | UNASSIGNED | BLOCKED | All SB tests implemented and green (IC-4) |
| TEST-004 | Agent golden tests with recorded responses | tests/ | — | TEST-001, SEC-006 | UNASSIGNED | BLOCKED | One recorded scenario per agent; schema-validated |

## Phase 4 — Monitor & learn (P3)

| ID | Title | Dir | Reqs | Depends on | Owner | Status | Acceptance criteria |
|---|---|---|---|---|---|---|---|
| MON-001 | GitHub webhook ingestion (HMAC, dedupe, raw store) | monitoring/, backend/ | FR-3-01 | CORE-006 | UNASSIGNED | BLOCKED | SB-10 passes; replayed fixtures processed idempotently |
| MON-002 | Normalization + correlation → ImpactSet | monitoring/ | FR-3-02 | MON-001, INTEL-008 | UNASSIGNED | BLOCKED | Push fixture maps to correct symbols/findings |
| MON-003 | Trigger policy + ReassessmentRequest + coalescing | monitoring/ | FR-3-03 | MON-002, SEC-012 | UNASSIGNED | BLOCKED | IC-7 passes |
| MON-004 | Runtime log signals from sandboxed demo target | monitoring/ | FR-3-04 | SEC-004 | UNASSIGNED | BLOCKED | Per-route signals computed from target logs |
| RL-001 | `DefenseSimEnv-v0` Gymnasium environment + configs | rl-defense/ | FR-3-05 | — | Adam | IN_REVIEW | `check_env` + determinism tests; train/eval configs separated; `rl.yml` CI |
| RL-002 | Baselines: random, noop, threshold_rules | rl-defense/ | FR-3-05 | RL-001 | Adam | IN_REVIEW | Thresholds tuned on train configs only |
| RL-003 | Double DQN training | rl-defense/ | FR-3-05 | RL-001 | Adam | IN_REVIEW | 5-seed runs with manifests; CPU smoke train < 5 min |
| RL-004 | Evaluation harness per protocol 17 | rl-defense/ | FR-3-05 | RL-002, RL-003 | Adam | IN_REVIEW | `eval_summary.json` + table with CIs for all policies and metrics |
| RL-005 | Inference → DefenseRecommendation + API endpoint | rl-defense/, backend/ | FR-3-06 | RL-004, CORE-004 | Adam | IN_PROGRESS | Recommendation stored with caveat; no action path (test) |

## Phase 5 — Integration, UI & demo

| ID | Title | Dir | Reqs | Depends on | Owner | Status | Acceptance criteria |
|---|---|---|---|---|---|---|---|
| UI-002 | Project/repo connect + scope request/approve screens | frontend/ | FR-P-02, FR-P-03 | UI-001, CORE-005, CORE-007 | UNASSIGNED | BLOCKED | Flows work against local API |
| UI-003 | Live assessment timeline (SSE) | frontend/ | — | UI-001, CORE-006 | UNASSIGNED | BLOCKED | Reflects real states; reconnects |
| UI-004 | Finding detail with evidence chain | frontend/ | NFR-03 | UI-003 | UNASSIGNED | BLOCKED | Every claim links to evidence; status badges |
| UI-005 | Approval inbox | frontend/ | FR-2-05 | UI-002 | UNASSIGNED | BLOCKED | Approve/decline remediation with summary |
| UI-006 | Patch diff + verification checks view | frontend/ | FR-2-06 | UI-004 | UNASSIGNED | BLOCKED | Shows each Verify check with evidence |
| UI-007 | Monitoring feed + RL recommendation panel | frontend/ | FR-3-06 | UI-001, MON-003, RL-005 | UNASSIGNED | BLOCKED | Caveat text always shown |
| TEST-005 | Demo-scenario e2e (`e2e.yml`) | tests/e2e | — | IC-1…IC-8 tasks, UI-006 | UNASSIGNED | BLOCKED | IC-9 green on clean stack |
| DEMO-002 | Demo rehearsal + offline fallback | — | — | TEST-005 | UNASSIGNED | BLOCKED | Checklist in [20](../20_DEMO_SCRIPT.md) complete |
| DEMO-003 | Pitch slides with traceable numbers | — | — | RL-004, TEST-005 | UNASSIGNED | BLOCKED | Every number cites a run ID or eval summary |

### Sarosh intelligence evidence (PR #6)

INTEL-001..008 were implemented on `feat/sarosh/code-intelligence` and merged through
PR #6. DONE covers the Python producer acceptance; complete runtime integration has separate gates. See [implementation](../../code-intelligence/README.md),
[producer evidence](../../code-intelligence/evidence/m1-payments-lite.json), and
[typed consumer fixture](../../code-intelligence/fixtures/payments-context-pack.json).
Local ingestion/graph/intent/context/diff tests and backend PostgreSQL/webhook integration
execute real code. FakeTransport covers inference; the opt-in live attempt skipped for
missing authorized key. Head facts are fully re-derived; parse caching, authenticated human
intent decisions, and full Sai/Alan runtime adapters remain explicit follow-ups.

Producer acceptance and CI passed; PR #6 merged as `bcc2e23`. INTEL rows refer to the implemented Python producer, not complete cross-pillar runtime integration. Final counts: 24 passed/1 skipped focused; 115 passed/4 skipped broader.

### Sarosh human-intent and verified-regression memory (PR #39)

Additive 0.6.0 contracts `ExpectationDecisionRequest`, `ExpectationDecision` and
`VerifiedRegression` are implemented with append-only PostgreSQL/SQLite stores,
authenticated backend routes, optimistic concurrency and an immutable audit trail.
Exact-snapshot decisions surface through `expectations`/context packs with
`human_input` evidence; independent Verify accepted candidates enqueue a durable,
deduplicated regression-join job. The reviewer and security host adapter consume
the same service. Evidence on the branch: backend/API/PostgreSQL **154 passed,
5 skipped**; code-intelligence/shared **62 passed, 2 skipped**; reviewer **48
passed, 1 skipped**; security agents **344 passed, 11 skipped**. Skips are
opt-in live provider, RL package/TypeScript compiler and sandbox-only tests.
Srihith's contract-owner acknowledgment remains pending before merge.

### Sarosh frontend transport assistance (issue #29)

UI-001 generated-contract client and UI-003 SSE transport substeps are implemented
in `frontend/transport/` (`d4a0fce`, `3bc4e28`, `05ce162`, `a48a202`). Vihaan retains
frontend ownership; the Next scaffold, rendered screens, browser auth and complete
UI-001/UI-003/M6 acceptance remain pending. No claim that the full task rows are
DONE. Evidence: 13 unit tests plus strict TypeScript; real HTTP/PostgreSQL parent
and three subtests passed, including durable SSE replay, CSRF, tenant denial and
abort. No provider or target execution occurred in transport tests.

## Standards integration follow-up

| ID | Objective | Owner | Status | Dependencies | Acceptance / integration / tests |
|---|---|---|---|---|---|
| STD-001 | Connect canonical PR #49 standards to persisted findings, incidents, reports and transport; cover OWASP editions | Srihith | IN_REVIEW on `feat/srihith/standards-alignment` | PR #49 canonical catalogs/contracts | Offline catalogs; reference scoring; host persistence; real PostgreSQL incident lifecycle/tenant/approval tests; generated types; truthful partial coverage. Rendered frontend integration remains separate. |
