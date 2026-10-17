# Alan — implementation status

Owner: Alan (`security-agents/`, SEC-001 … SEC-013)
Branch: `feat/alan/seven-agent-runtime`
Current task: host integration, durable approval recovery and indexed-context verification
Last remote sync: 2026-10-17T02:05Z — merged `origin/main` @ `9beccf4` (shared V0, backend, canonical payments-lite)
API/contract dependencies: `shared` V0 (acked with 6 deltas), `backend.host` (adapter written, unverified), `code_intelligence.api` (port + local adapter), `code_review` (shares my sandbox)
Recent PR/commit: `b0ae682` on `feat/alan/seven-agent-runtime` (PR to open)
Blockers: none blocking; 2 open questions to Srihith (host re-entry state, indexed workspace)
Next action: finish CI/review on PR #35; live-provider and Docker gates remain opt-in/unverified here

## What runs today

| Task | What exists | Evidence |
|---|---|---|
| SEC-001 | `AgentSpec` + bounded agent loop: budgets (token/usd/turn/tool-call/wall-clock), one schema-repair retry, cancellation, kill switch, redacted transcripts | `tests/test_runtime_loop.py` (17) |
| SEC-002 | Tool registry with the docs/07 capability matrix, typed args, scope enforcement, audit; `scope_guard` pure | `tests/test_tool_registry.py` (51), `tests/test_scope_guard.py` (24) |
| SEC-003 | Sandbox driver: pinned snapshots, profiles, network modes, limits, timeout, env scrubbing, reaper; hardened Docker argv | `tests/test_sandbox.py` (33) |
| SEC-004 | Check-runner path against the authorized target, scope-gated at the driver | `tests/test_checks.py` (19) |
| SEC-005 | Check-template library v0: `access_control.ownership@1`, `input_validation.bounds@1`, rendered from the scope-approved build recipe, deterministic `matches_expectation`, fails closed when unreviewed | `tests/test_checks.py` |
| SEC-006 … SEC-009, SEC-011, SEC-013 | Scout, Probe, Trace, Diagnose, Patch, Fortify: own prompt, I/O schema, tool set, budget, and deterministic post-processing | `tests/test_agent_logic.py` (47) |
| SEC-010 | Verify: own run, fresh checkout, fresh sandboxes, no Patch transcript, verdict computed from the 5 checks | `tests/test_agent_logic.py`, `tests/test_e2e_replay.py` |
| SEC-012 | Orchestrator state machine, gates, per-finding remediation sub-flow capped at 2 attempts, hash-chained audit | `tests/test_states.py` (47), `tests/test_e2e_replay.py` (28) |
| — | Export adapter onto canonical `shared` V0 | `tests/test_contracts.py` (16) |
| — | `AssessmentHost` adapter (`build_orchestrator().run(host)`) | `tests/test_host_adapter.py` (11) |
| — | Security-boundary suite (SB-07, SB-08, SB-11, SB-12 + the SB map) | `tests/test_security_boundaries.py` (32) |

## Verified tests

```
cd security-agents && .venv/bin/python -m pytest tests -q
325 passed, 3 skipped in 88.51s
cd security-agents && .venv/bin/python -m ruff check security_agents tests
All checks passed!
```

The 3 skips are the opt-in live-provider tests; they run only with
`RUN_LIVE_LLM_EVAL=1` and credentials.

End-to-end on the canonical owned target (`examples/payments-lite/target`),
scripted model turns and **real** tool authorization, sandboxes, diff and tests:

```
cd security-agents && .venv/bin/python -m security_agents.cli --target ../examples/payments-lite --auto-approve
scope_check -> indexing -> functional_review -> recon -> validation -> analysis
  -> diagnosis -> awaiting_approval -> remediation -> hardening -> reporting -> completed
scout/probe/trace/diagnose/patch/verify/fortify: all succeeded
[hardened] Payment detail route may not enforce payment ownership
  class=CWE-639 severity=high validation=confirmed verdicts=['accepted']
  regression test: tests/test_authz_regression.py
provider_modes=['fake']
```

Executed check results on the fixture (the precision evidence):
`access_control.ownership@1` returns `matches_expectation=False` on the planted
`GET /payments/{payment_id}` and `True` on the negative
`GET /customers/{customer_id}`; `input_validation.bounds@1` returns `False` on
`POST /refunds`.

## Honest status of what is NOT verified

- **No live-provider run has been executed.** Every number above comes from the
  scripted (`fake`) provider. The live path is implemented
  (`AnthropicProvider`, `claude-opus-5-5` default, per-role overrides, refusal
  fallback, typed error mapping) and the opt-in tests exist, but they have not
  run — no authorized key in this environment (issue #10). Until they do, the
  live mode is **UNVERIFIED**.
- **The Docker sandbox driver has never executed a container here.** Its
  argument construction, policy checks and reaper are unit-tested with a fake
  command runner; there is no Docker engine on this machine and no pinned image
  yet (INFRA-005). The development driver that the tests use is a subprocess
  with scrubbed env, rlimits, a copied workspace and a Python-level network
  guard — it reports `isolation_level="process-dev:not-a-security-boundary"` and
  refuses to start without an explicit opt-in. It is adequate only for the
  fixtures we own.
- **The host adapter has not run against the real `backend.host`** (needs
  Postgres and the artifact store). It is tested against a fake host built from
  `backend/INTEGRATION.md` and `backend/backend/{host,llm}.py`.
- **Expectations are a labelled fixture, not derived.** They come from
  `examples/payments-lite/labels.yaml` (`expectations:` only, `origin="fixture"`)
  until `code_intelligence.api` lands. The answer-key sections are never read by
  an agent.
- **Probe's template library has two templates.** Both are reviewed by me and
  marked `reviewed_by="security-owner:pending-human-signoff"` — a human security
  owner has not signed them off, and a template with `reviewed_by=None` is
  refused at runtime.

## Session entries

### 2026-10-17 (session 1)

- Read `MASTER_BUILD_SPEC.md`, `AGENTS.md`, `CLAUDE.md`, the coordination files,
  `team-prompts/ALAN_IMPLEMENTATION.md` and the subsystem specs (docs/07, 08,
  12, 15, 16, agents/*). Checked GitHub: at session start there were no branches
  besides `main`, no PRs and no messages.
- Implemented SEC-001 … SEC-013 on `feat/alan/seven-agent-runtime`:
  contracts adapter, LLM providers (live/fake/replay), scope guard, tool
  registry + catalog + services, sandbox (workspace, local and Docker drivers,
  in-sandbox entrypoint), check-template library, code-intelligence port and
  local adapter, agent runtime, the seven agents, the orchestrator, the CLI.
- Wrote and executed the test suite; it found three real defects in my own code:
  a plain `Path` workspace resolving to the filesystem root (`Path.root` exists),
  a call-graph self-resolution bug, and a redactor that missed a secret glued to
  other characters. All three fixed with a pinning test.
- Synced with `origin/main` after Srihith's PR #8 merged: took Adam's canonical
  `examples/payments-lite/` (`target/` + `labels.yaml`), dropped my own flat
  variant of the same fixture, added `build_recipe.json`, generalised the bounds
  template for the real API shape, and rewrote the scripted trajectories so the
  fix is the missing `require_owner` call.
- Built the export adapter onto `shared` V0 with 16 contract tests, which
  surfaced six field-level mismatches; acked the contracts and sent the deltas.
- Implemented Srihith's `AssessmentHost` interface so the backend worker can run
  the pillar, with the approval round-trip, and sent the two open questions.
- Messages sent: contracts ack + deltas (srihith), shared repair sandbox (sai),
  code-intelligence port (sarosh), agent UI fields (vihaan).

### 2026-10-16 — Codex continuation
- Resumed Claude worktree, fast-forwarded Alan branch to origin/main d8ad0cb.
- Fixed live-run numeric schema rejection (3fea691) and false clean assessment after Scout failure.
- Executed runtime/schema/intelligence tests: 28 passed; Scout failure regression: 1 passed; ruff clean. Broader replay suite running at checkpoint. No live API call made.
- Next: backend host-mode compatibility findings remain; live rerun requires credentials/authorized budget.

- Completed replay/schema verification: 31 passed in 45.60s. Both fixes pushed as 3fea691 and efbc848.

- Host adapter continuation: aligned property access, populated actual role run IDs, and passed gateway usage/tool records to finish_agent_run. Host unit suite: 12 passed; Ruff clean. PostgreSQL acceptance in progress.

- Hardened host defaults and scope adaptation: 21 host tests passed, Ruff clean; real PostgreSQL host acceptance now 1 passed (removed obsolete xfail). Docker execution remains unverified.

- Durable approval resume implemented via additive host checkpoint API (hashed artifact + assessment-scoped event pointer). Host suite: 23 passed, Ruff clean; real backend fresh-factory resume: 1 passed. Checkpoint isolation/integrity suite in progress.

- Host now pins execution to assessment SHA through trusted bindings and consumes upstream intelligence (34 host/index tests passed). Full real PostgreSQL host flow with actual Git SHA, indexed context and fresh-factory approval resume: 1 passed. Full pre-binding security suite: 350 passed, 4 skipped.

- Integrated main's single-host reviewer/security path (c0b5136 / #36) without losing checkpoints or fail-closed authorization. Preserved the upstream canonical test rename. PostgreSQL reviewer + security + restart/gates subset: 10 passed. Pre-merge full workspace: 149 passed, 5 skipped; security runtime: 355 passed, 4 skipped. Re-running both after merge.

### 2026-10-17 — recovered Claude standards continuation
- Inspected Claude's dirty worktree and remote PRs; preserved all changes, leaving unrelated .codex files untouched.
- Reviewed and merged PR #69 after all CI checks passed.
- Completed canonical CVSS3.1/OWASP API/NIST800-115 consolidation, fixed OWASP API framework identity, and delegated the legacy calculator to the canonical package.
- Executed standards + runtime standards suites: 300 passed (offline). No live model or sandbox claim.
- Next: sync remote runtime branch/main, verify broad integration, and resolve remaining PR #35 browser e2e gate before merge.

- Fixed PR #35 browser regression: bound host intake now prefers the backend's shared intelligence service and attaches the exact snapshot instead of requiring independent service configuration.
- Executed 12 indexed-host tests, 7 PostgreSQL host/unified/memory tests, and the real Next/FastAPI/PostgreSQL/worker browser stack: 8 passed (10.4s). Scripted models and explicitly scoped local fixture execution; no live/Docker claim.
