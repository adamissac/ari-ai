# MSG: Integrating the seven-agent runtime with the backend — three blockers + adapter plan
- ID: `20261017T015103Z-srihith-to-alan-orchestrator-integration`
- From: srihith
- To: alan (cc: adam, sarosh, sai)
- Kind: `blocker`
- Timestamp (UTC): 2026-10-17T01:51:03Z
- Branch / commit / PR or issue link: `origin/feat/alan/seven-agent-runtime` @ `c417b77` (no PR yet); backend host contract in `backend/INTEGRATION.md` on main
- Related subsystem(s): security-agents ↔ backend worker/AssessmentHost ↔ examples/payments-lite ↔ shared
- Summary (facts, not assumptions): I read `security_agents.api`, `workflow/orchestrator.py`, `contracts/models.py`, `tests/test_e2e_replay.py` and `tests/conftest.py` on your branch. The runtime is real: seven role loops, a tool registry, scope_guard, an executed check, a worktree diff and an independent Verify. Three things block hosting it from the backend:
  1. **Base is stale.** Your branch is based on `945afc9`. `main` now has shared contracts 0.3.0, the backend, Adam's payments-lite (PR #5) and CI.
  2. **payments-lite conflict.** Your branch adds `examples/payments-lite/{build_recipe.json,expectations.json,payments_lite/,tests/}`. Adam's merged DEMO-001 uses `examples/payments-lite/target/{payments_lite,tests,Dockerfile,pyproject.toml}` plus `labels.yaml` and `label_checks/`, and has no `build_recipe.json` or `expectations.json`. Your conftest `PAYMENTS_LITE` path and `build_recipe_ref` will break on rebase. Please agree with Adam on one layout, presumably main's, with recipe and expectations added under `target/` if you need them.
  3. **Duplicate contracts.** `security_agents/contracts/models.py` re-declares `EvidenceRef`, `AuthorizedScope`, `Approval`, `Finding` parts, `AgentRun`, `Usage` and `AuditEvent`, and some fields differ from `shared`:
     - `EvidenceRef` has no `kind`/`sha256` and uses a different `provenance` enum;
     - `Approval` has `decision` instead of `status`;
     - `ScopeTarget` has `target_id`;
     - `PatchCandidate` has `diff_uri` instead of `diff_artifact_id`;
     - `VerificationResult` has `verify_run_id` instead of `produced_by_run_id`.

     Per MASTER_BUILD_SPEC §3 these should come from `shared`. Send field proposals (e.g. `ScopeTarget.target_id`, `Hypothesis.entry_point_id`, `ValidationResult.observations`, `AgentRun.llm_turns`) to me and I'll add them as additive 0.4.0 fields.
- Interface requested/proposed (field-level types/example payload): I'm building `backend.adapters.security_agents:build_orchestrator` (backend-owned, no edits to your path). It hosts your `Orchestrator` inside the worker:
  - **Live mirroring:** state transitions go to `host.transition` (SSE), each agent step to `host.start_agent_run`/`finish_agent_run` with usage charged to the assessment budget, and findings, patches and verifications to host records. A diff is stored as an artifact, and `verify_run_id` maps to the host run id, so the backend's Verify-independence gate applies.
  - **Approval:** `approve_remediation` creates a real pending `remediation` approval (subject_id = plan id) and waits for the human decision while the job lease heartbeats. A timeout or decline goes to REPORTING, matching docs/08.
  - **Sandbox:** `DockerSandboxDriver` by default. `LocalProcessDriver(allow=True)` only with `SECURITY_SANDBOX=local-dev` in development or test, for the owned demo target.

  To avoid subclassing your private `_goto`/`_run_step`, please add public hooks to `Orchestrator.__init__`: `on_transition(src, dst, note)` and `on_step(spec, ctx, outcome)`. Also please expose `SnapshotHandle.from_git` usage for a bound repo checkout, which is already there.
- Breaking change? migration/test impact: Rebasing touches `examples/` (conflict) and your conftest paths. There is no backend impact.
- Action required by recipient: (a) rebase on `origin/main` and resolve payments-lite with Adam; (b) ack or counter the hook names; (c) send contract field proposals; (d) open a PR so CI runs your suite.
- Response-by milestone (not invented clock time): before M3 gate.
- Evidence: `git ls-tree origin/feat/alan/seven-agent-runtime -- examples` versus `git ls-tree origin/main -- examples/payments-lite`; `git merge-base origin/feat/alan/seven-agent-runtime origin/main` = `945afc9`.
- In-Reply-To (optional): —
