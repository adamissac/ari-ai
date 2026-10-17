# Alan — implementation status

Owner: Alan (`security-agents/`, SEC-001 … SEC-013)
Branch: `feat/alan/standards-roe-wiring`
Current task: standards addendum P0: RoE gate, CVSS v3.1 level, CWE/OWASP/ATT&CK/D3FEND wiring on canonical `standards/`
Last remote sync: 2026-10-17T10:05Z, `origin/main` @ `de4967f` (#98 merged)
API/contract dependencies: `shared` 0.9.0 `CheckCategory`; `backend.host` checkpoints; `code_review.api` functional helpers
Recent PR/commit: `feat/alan/verify-honesty-check-category` (do not push merged `host-finding-persistence` / `host-resume-hardening`)
Blockers: live seven-agent run (issue #10, no key); Docker images (INFRA-005)
Next action: land standards-roe-wiring PR; Srihith decision on v3.1 shared field and RoE endpoint; Adam decision on CWE-840 fixture

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

### 2026-10-17 (verify honesty + CheckCategory)

- Kept #84 `provider_mode="none"` for functional Verify. Canonical `CheckCategory`
  with Probe ids + fixture aliases. `SCHEMA_INVALID` regression for recipe
  `target_dir`. Message: `20261017T092222Z-alan-to-srihith-check-category-canonical.md`.

### 2026-10-17 (Codex P1/P2 after #73 merged)

- #73 is on main. Did not push the merged branch. All seven Codex items were
  missing from `origin/main`; implemented on `feat/alan/host-resume-hardening`.
- Message: `20261017T085211Z-alan-to-srihith-host-resume-hardening.md`.

### 2026-10-17 (Srihith follow-up c75a56e on #73)

- Ported `_report_or_wait` + unconditional `external_pending` pause from
  `feat/srihith/functional-remediation` @ `c75a56e`. Did **not** merge #71.
- Complete-run functional reproduction was already `_functional_reproduced`
  on this branch; added hang/`exit_code=None` to the guards test.
- Message: `20261017T083214Z-alan-to-srihith-ported-c75a56e-pause-gates.md`.

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

### 2026-10-17 — Codex recovered catalog consolidation
- Preserved Claude's uncommitted catalog work as 93c0225 on PR #35, with subsequent integration fixes committed/pushed.
- Reviewed/merged PR #69 with all CI green. PR #73 is a newer focused host/functional-Verify implementation; PR #35 will be superseded once unique fixes are preserved.
- Isolated canonical CVSS3.1, OWASP API2023 and NIST800-115 package additions onto feat/alan/recovered-catalogs, excluding the duplicate legacy security-agents standards tree and schema projection.
- Standards/runtime standards source tests passed 300 offline; narrow canonical tests will be rerun here. Earlier recovered runtime passed 524 tests (11 optional skips), root 358 (6 optional skips), browser 8. These counts belong to PR #35 and are not claims about this new branch.
- Exact .gitleaksignore fingerprint is a public OWASP source commit, not a credential; full-history scan clean and synthetic credential detection remains enforced.

### 2026-10-17 — Codex host-recovery hardening
- Continued PR #73 after isolating unique catalog recovery in PR #74. Preserved fail-closed scope/budget/human-approver mapping from #35; resume reloads authorization and rebinds the current worker host.
- Functional Verify requires actual failed assertions on every generated test file and recorded sandbox runs; errors, timeout, empty tests, skipped generated tests, source overwrite and test overwrite are rejected. Added 19 negative/authorization regressions (36 focused tests passed).
- Adopted PR #71's two-approval browser harness without merging its competing host implementation. Browser e2e: 8 passed (23.1s).
- Full root suite: 324 passed, 6 optional skips. Security suite: 379 passed, 11 opt-in/optional skips. Ruff/format/mypy pass. No new live-provider or Docker proof.
- PR #35 remains recoverable and will be superseded by #73/#74; no work discarded. Merge these only after current-head CI passes.

## Standards addendum (P0) on `feat/alan/standards-roe-wiring`

| Item | What exists | Evidence (offline) |
|---|---|---|
| Pinned indexes | CWE 4.20, ATT&CK Enterprise 20.0, D3FEND 1.6.0, OWASP API 2023, OWASP LLM 2026, CVSS v3.1 and v4.0, NIST SP 800-115; sha256 in `standards/standards/data/MANIFEST.json` | `standards/tests` 189 passed |
| CVSS v3.1 | `standards/standards/cvss31.py`, 34 NVD vectors plus property tests; level derives from the computed rating (ADR-0012) | `standards/tests/test_cvss31.py` |
| Rules of engagement | `security_agents/standards/roe.py`; registry gate fails closed with SCOPE_DENIED and `tool.roe_denied` | `tests/standards/test_rules_of_engagement.py`, `tests/standards/test_negative.py` |
| Agent wiring | Scout CWE plus OWASP API tag from code; Trace v3.1 metrics with evidence or unverified, optional ATT&CK; Diagnose and Fortify optional D3FEND | `tests/test_agent_logic.py`, `tests/test_e2e_replay.py` |

```
cd security-agents && .venv/bin/python -m pytest tests -q        # 441 passed, 10 skipped
.venv/bin/python -m security_agents.standards.report            # 217 standards tests, 0 failed, UNVERIFIED: NVD licence terms
.venv/bin/python -m security_agents.standards.smoke             # writes standards-smoke-output/{finding.tagged.json,rules_of_engagement.json,sp800115_coverage.json}
```

UNVERIFIED: NVD terms page (Cloudflare challenge). All runs above are replay or offline; no live Claude call.
