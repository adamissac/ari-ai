# Alan — implementation status

Owner: Alan (`security-agents/`, SEC-001 … SEC-013)
Branch: `feat/alan/host-finding-persistence`
Current task: finding lifecycle + durable approval resume + functional Verify on the host path
Last remote sync: 2026-10-17T08:05Z — merged `origin/main` @ `03323cd` (#69 standards follow-up, #70 Sai status)
API/contract dependencies: `shared` V0, `backend.host` (`save_checkpoint` / `load_checkpoint` / `set_finding_status`), `code_review.api` functional helpers (#68)
Recent PR/commit: this branch (draft PR to main)
Blockers: live seven-agent run (issue #10, no key); Docker images (INFRA-005); PR #35 should be **closed**, not merged
Next action: land this PR; comment on #35; Vihaan re-check finding status in the UI

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

### 2026-10-17 (host finding persistence)

- Branch `feat/alan/host-finding-persistence` off current main. Did not continue
  `feat/alan/security-standards` or merge PR #35.
- `HostSink` persists finding status/history; checkpoint save/load resumes after
  `pipeline._ORCHESTRATORS.clear()`; functional repair + five-check Verify via Sai's
  `functional_verification_inputs`; `tool_calls` / `sandbox_seconds` charged.
- Tests actually run: `make check`; host-adapter 16 passed; unified + host-mode +
  e2e-host included in 27 passed after merging main.
- Messages: srihith (checkpoints/lifecycle), sai (functional Verify wired),
  vihaan (status no longer stuck at hypothesis).

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
