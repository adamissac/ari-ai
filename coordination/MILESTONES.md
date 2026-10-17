# Integration milestones and evidence requirements

- [x] **M0** shared schemas, importable packages, reproducible local run commands, PR/branch conventions agreed. Gate: 6 owners acknowledge types; CI contract tests pass.
- [x] **M1** intelligence indexes the owned Python example by SHA, structured graphs, expectations and citeable context packs. Gate: tests and provenance inspection.
- [x] **M2** reviewer with real Claude agent loop can interpret commit intention, call retrieval/tests, generate candidate in safe worktree, inspect results. Gate: live optional smoke and deterministic fixture tests; functional defect reproduced.
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
  - Docker is not installed locally, but CI's `containers` workflow builds the image (`backend-image`) and smoke-runs the Compose stack (`compose-stack`) on every PR.

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


### M0 evidence — Srihith

- Issue #9 has ACKs from all six owners: Sarosh, Adam, Alan, Sai, Vihaan, plus Srihith as contract owner.
- The contracts evolved additively to `SCHEMA_VERSION` 0.8.0.
- Every PR runs `uv run python -m shared.export --check` and `uv run python -m shared.examples --check` (the backend workflow), and the transport validates every wire DTO against `shared/generated/contracts.schema.json`.
- Run commands are in CLAUDE.md "Commands". Branch and merge conventions: issue #12.


### M2 evidence — Sai

Gate: live optional smoke + deterministic fixture tests; functional defect reproduced.

- **Real Claude agent loop, live (Tier 3).** Adam ran it with the owner's key on payments-lite;
  this agent spends nothing. Command: `RUN_LIVE_LLM_EVAL=1 uv run pytest -q -m live_llm code-review/tests/test_live_reviewer.py -s`.
  - Run 1 (main @ `0612cc5`): PASS. Review found the refund bound (TP, FP 0, FN 0) with a generated test
    failing on the unpatched target; repair `accepted_locally` ($0.276 + $0.082). It exposed a span-verifier
    bug (security hand-offs dropped), fixed in #59.
  - Run 2 (main @ `cdfc679`, after #59): PASS. Refund-bound TP, `generated_tests_failing_on_head: 2`,
    `security_handoffs_matched: [fnd_planted_authz]` (IDOR handed to Scout), 0 rejected spans, repair accepted
    ($0.374 + $0.115). Source: `coordination/messages/20261017T070325Z-adam-to-all-live-p1-p2-handoff-works.md`.
  - Srihith's live unified run: the reviewer produced 2 validated findings ($0.37)
    (`coordination/messages/20261017T024043Z-srihith-to-alan-sai-first-live-unified-run.md`).
- **Deterministic fixture tests (CI).** `.github/workflows/code-review.yml` runs strict mypy, ruff and
  `pytest code-review/tests` on Postgres 16: **60 passed, 1 skipped** (the opt-in live test). Coverage:
  intent adjudication (confirmed/inferred/ambiguous/conflicting, human decisions from the real intelligence
  memory), retrieval through the real code-intelligence index, sandboxed generated tests (assertion vs
  tooling errors, reproducibility, base-commit control), approval-gated repair in an isolated export with a
  fresh replay, protected-test tampering refusal, authorization → Scout hand-off, CWE adjudication, and the
  real `AssessmentHost` flow with independent Verify.
- **Functional defect reproduced and repaired.** payments-lite `fnd_planted_refund_bound`: the generated test
  fails twice with AssertionError on head; the approved repair (`already + body.amount > p.amount`) passes it
  and the existing suite in a fresh replay. Since #73 the hosted flow takes that patch through an independent
  functional Verify to `verified` (`backend/tests/test_unified_assessment.py`).

Limitations: live runs are opt-in and were run by a key holder, not in CI. Update: reviewer tests now also run
inside the real Docker sandbox in CI (`docker-reviewer` job, #127, GitHub Actions run 39028078294: 2 passed:
kernel-level `--network none`, no host-env leak, defect validated in a container).


### M3 evidence (partial, gate NOT met) - Alan

Gate: observed real model/tool trace per required role (opt-in), fake-provider integration tests, separated Verify actual tests.

- **Fake-provider integration (CI-equivalent, executed).** `cd security-agents && .venv/bin/python -m pytest tests -q`: 442 passed, 10 skipped (opt-in live) on `feat/alan/standards-roe-wiring` merged with `origin/main` @ `64995dc`. Seven `AgentSpec`s with distinct prompts, tool sets, budgets and schemas (`tests/test_agent_logic.py`, `tests/test_runtime_loop.py`); tool permission matrix and scope plus rules-of-engagement gate before every scope-required call (`tests/test_tool_registry.py`, `tests/standards/test_rules_of_engagement.py`, `tests/standards/test_negative.py`); typed handoffs exported to `shared` (`tests/test_contracts.py`); full replay chain with real sandboxes, diff and tests (`tests/test_e2e_replay.py`).
- **Separated Verify (executed).** Verify runs in its own sandbox and fresh checkout without the Patch transcript; the verdict is computed from executed checks (`tests/test_agent_logic.py::test_verify_*`, `tests/test_e2e_replay.py`).
- **Live trace per role: NOT observed.** The only live attempt (2026-10-17T02:40Z, Srihith) stopped at Scout with an API 400 on integer `minimum` in tool schemas; fixed in `3fea691` (`tests/test_provider_schema.py`), never re-run. The opt-in test `tests/test_live_provider.py::test_live_seven_roles_end_to_end` now runs the full orchestrator live on payments-lite with a spend cap and asserts a live model turn for each of the seven roles, writing `tests/artifacts/live/*-seven_roles_end_to_end.json`.
  Command for a key holder: `cd security-agents && RUN_LIVE_LLM_EVAL=1 LIVE_SEVEN_MAX_USD=8 .venv/bin/python -m pytest -q -m live tests/test_live_provider.py -s`

Limitations: no authorized key in Alan's environment (issue #10). Docker sandbox unexecuted (INFRA-005); local-process driver is not a security boundary.
