# Alan — implementation status

Owner: Alan (`security-agents/`, SEC-001 … SEC-013)
Branch: `fix/alan/main-health`
Current task: keep security-agents claims accurate; M3 live run pending a key holder
Last remote sync: 2026-10-17, `origin/main` @ `39186cb`
API/contract dependencies: `shared` 0.9.0 `CheckCategory`; `backend.host` checkpoints; `code_review.api` functional helpers
Recent PR/commit: `feat/alan/verify-honesty-check-category` (do not push merged `host-finding-persistence` / `host-resume-hardening`)
Blockers: live seven-agent run (issue #10, no key); Docker images (INFRA-005)
Next action: live seven-role run by a key holder (M3); human sign-off on the two check templates

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

Executed on `origin/main` @ `39186cb`, 2026-10-17:

```
cd security-agents && .venv/bin/python -m pytest tests -q
451 passed, 18 skipped in 82.57s
uv run pytest -q          # repo root testpaths (shared, monitoring, backend, code-review, standards, tests/security)
415 passed, 9 skipped in 75.46s
```

Skips: opt-in live-provider tests, and Docker tests that run only in the CI
`docker-sandbox` / `docker-reviewer` jobs (6 passed there on `719ce98`).

## Honest status of what is NOT verified

Updated 2026-10-17 after #100 to #125.

- **No live-provider run of the seven agents has been executed (M3 open).** Every
  security-agents number comes from scripted model turns with real tools, sandboxes
  and tests. The only live attempt stopped at Scout on a tool-schema 400 (fixed since).
  `tests/test_live_provider.py::test_live_seven_roles_end_to_end` is ready for a key
  holder (issue #10). Live mode stays **UNVERIFIED** until it runs.
- **Docker sandbox: verified in CI for the paths we use.** The `docker-sandbox` job
  builds `security-agents/sandbox/Dockerfile` (digest-pinned python:3.12-slim) and passes
  6 real-container tests: uid 65534, read-only root, a raw socket blocked by the kernel,
  no host env, timeout kill and removal, the payments-lite suite, and the reviewed
  ownership and bounds checks with the same verdicts as the local driver. Sai's
  `docker-reviewer` job reuses the image. Not verified: v0 checks call the app in process
  (`TestClient`), so the target container and `--internal` network are created but no
  check sends traffic over them. The CI image tag is local, so the job sets
  `SANDBOX_ALLOW_UNPINNED_IMAGE=1` (the base is pinned).
- **Host adapter: runs against the real `BackendHost` on PostgreSQL in backend tests**
  (`backend/tests/test_security_agents_host_mode.py`, `test_m7_push_to_regression.py`,
  `test_standards_host_integration.py`, `test_roe_persistence.py`), with scripted model
  turns. Not verified: a deployed worker against a live repository.
- **Expectations.** Hosted runs use the shared code-intelligence index when the
  repository is bound (`intel.host_service.shared_host_intel`). Directory fixtures fall
  back to `SECURITY_AGENTS_LABELS` (dev/test only; the backend host-mode test sets it).
  The answer-key sections of labels.yaml are never read by an agent.
- **Probe's template library has two templates.** Both are marked
  `reviewed_by="security-owner:pending-human-signoff"`; no human security owner has
  signed them off. A template with `reviewed_by=None` is refused at runtime.
- **Standards.** The NVD terms of use for the 34 pinned CVSS v3.1 vectors are
  UNVERIFIED (Cloudflare challenge). OWASP API and LLM data are CC BY-SA 4.0; we store
  only ids and titles. Everything is "mapped to" or "aligned with"; no certification is
  claimed.

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

### 2026-10-17 — Docker evidence reconciliation
- Confirmed #73/#74 merged, #35 closed, and no open PRs at session start. Preserved the primary Devin checkout and its untracked reports.
- Verified security CI 39033028814 on main `5b3ef50`: 6 real-container tests passed and ordinary security suite 451 passed/18 skipped. Reviewer Docker CI 39028078294 also passed.
- Corrected stale README integration dependencies and Docker-unverified claims in README/milestone/task evidence. No new live provider or local Docker run; published sandbox image digests and live seven-role proof remain open.

### 2026-10-17 — QA-002 M7 runner continuation
- Fixed the remaining Devin M7 runner's uv dependency/shared-db lifecycle operations and moved generated output into ignored .dev/qa (overridable). Exact current interpreter is retained; live calls forced off.
- QA runner13 tests passed; actual M7 backend workflow passed against PostgreSQL. Wrapper correctly exits2 for unexecuted browser stage. Full current security451 passed/18 skipped and standards190 passed earlier this session.

### 2026-10-17 — Codex application integration sprint
- Isolated checkout /private/tmp/omen-codex-integration, exact base37b0920c37d0460ecf988126693e79761478a888. Claude security-agent lane left untouched.
- API-RETRY-001 checkpoint d3320be: PostgreSQL transaction serialization and project-bound request digest prevent duplicate assessment starts and wrong-project cached acceptance. Before-fix reproduction2 failed; after-fix focused16 passed.
- Required suites: root420 passed/9 optional skips; backend79 passed/5 optional skips. Lint/format/mypy/contracts/links clean. Actual PostgreSQL/handlers/jobs; scripted providers. No new browser/live/Docker proof.
- PR for review only, no automatic merge. Compatibility note: old cached keys conflict after upgrade (fresh keys for new actions). Existing raw/stored patch hash issue155 remains in Claude's lane.

### 2026-10-17 — Codex explicit assessment conflict recovery
- fix/alan/explicit-conflict-recovery, own worktree from d1d324d. Reproduced absent reset and cross-project key retention (2 failed tests);3 targeted and70 frontend unit tests now pass. TS/lint/production build pass.
- Actual Chrome13 passed, including real409, retained-key retry, explicit preparation with zero requests, then exactly one new accepted assessment/job. Normal network-error retries keep the key; project identity is in the key signature. No product API or security changes.
