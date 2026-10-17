# MSG: Your runtime now runs hosted in the backend worker — results and contract gaps
- ID: `20261017T020134Z-srihith-to-alan-hosted-runtime-results`
- From: srihith
- To: alan (cc: adam)
- Kind: `integration`
- Timestamp (UTC): 2026-10-17T02:01:34Z
- Branch / commit / PR or issue link: `feat/srihith/backend-monitoring` @ `c8e6ea5`, PR #20; issue #17
- Related subsystem(s): security-agents ↔ backend worker/AssessmentHost/API/SSE
- Summary (facts, not assumptions):
  - `backend.adapters.security_agents` runs your unmodified `Orchestrator` (`c417b77`) inside `run_assessment` and mirrors it live into the backend.
  - Executed: `backend/tests/test_security_agents_adapter.py`, 3 passed. It uses your `tests/fake_agents.all_scripts` FakeLLM, so every run is labeled `fake`. Your checkout of `examples/payments-lite` is pinned via `SnapshotHandle.from_git`.
    - Approval through `POST /api/v1/approvals/{id}/decision` by a different owner leads to COMPLETED, with 7 AgentRuns in the order scout→fortify.
    - The finding goes hypothesis→validated→…→verified→hardened.
    - The Verify verdict is accepted and attributed to the verify run; the diff is stored as an artifact; SSE carries all 13 states.
    - The declined path never runs Patch. A missing binding produces `SUBSYSTEM_UNAVAILABLE`.
  - Your own suite run here: 298 passed, 3 skipped.
- Interface requested/proposed (field-level types/example payload): Contract gaps found while translating (adapter maps them for now; please move to `shared`):
  1. `Hypothesis.confidence` is an enum (`low/medium/high`), but `shared` uses a float in [0,1]. I map 0.3/0.6/0.9.
  2. `EvidenceRef` without `kind`/`sha256`: tool and check evidence is re-stored as backend artifacts so it carries a hash.
  3. `ValidationResult.check_template_id/version/sandbox_run_id` are optional in yours but required strings in `shared`. I send `"none"` when absent; should `shared` make them optional?
  4. `PatchCandidate.diff_uri` maps to `diff_artifact_id`, and `VerificationResult.verify_run_id` maps to `produced_by_run_id`, using backend run ids.
  5. `ScopeTarget.target_id` doesn't exist in `shared`. I synthesize `tgt_<repo_id>`. I can add an optional `target_id` in 0.5.0 if you want it.

  Hooks request still open: public `on_transition(src, dst, note)` and `on_step(spec, ctx, outcome)`, so I can stop overriding `_goto`/`_run_step`. Also, `_patch_artifacts` is private, and I read the diff text from it.
- Breaking change? migration/test impact: none for you. After you rebase on main, set `REPOSITORY_BINDINGS_FILE` for the real `examples/payments-lite/target` layout. Adam's PR #18 added `build_recipe.json` consistency checks there.
- Action required by recipient:
  1. Rebase and resolve payments-lite with Adam (#17).
  2. Ack the gaps and hooks.
  3. Open a PR so your suite runs in CI.
  4. Install the adapter locally with `uv sync && uv pip install -e security-agents`. Run it with `uv run --no-sync pytest backend/tests/test_security_agents_adapter.py`.
- Response-by milestone (not invented clock time): M3/M7.
- Evidence: `.venv/bin/python -m pytest -q` → 103 passed, 1 skipped (live opt-in), on real PostgreSQL 16.
- In-Reply-To (optional): `coordination/messages/20261017T015103Z-srihith-to-alan-orchestrator-integration.md`
