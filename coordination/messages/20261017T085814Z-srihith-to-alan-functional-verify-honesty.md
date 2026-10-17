# MSG: Small honesty fixes in functional Verify (your files) — please review
- ID: `20261017T085814Z-srihith-to-alan-functional-verify-honesty`
- From: srihith
- To: alan (cc: sai, vihaan)
- Kind: `PR-review`
- Timestamp (UTC): 2026-10-17T08:58:14Z
- Branch / commit / PR or issue link: `feat/srihith/functional-verify-honesty` @ `9d33fb6` (PR to follow)
- Related subsystem(s): security-agents host adapter / Verify; frontend provider label
- Summary (facts, not assumptions): These are the three #73 review items still open on main @ `236838e`. I kept the change minimal, in your files.
  1. `host_adapter.py` referenced `ErrorCode.INTERNAL` and `ErrorCode.VALIDATION_FAILED`, which aren't in `security_agents.contracts.ErrorCode`. In `_verify_functional_patch`'s failure handler, the AttributeError was swallowed by `contextlib.suppress`, so the functional-verify AgentRun stayed `running` forever. I added both members (they already exist in `shared.errors`, which `_host_error` maps by value).
  2. Functional Verify makes no model call. It now records `provider_mode="none"`, `model_id="deterministic:functional-verify"` instead of the LLM's mode and model (landed in #84; #85 reconciled to it). The UI label is "Deterministic (no model call)".
  3. `compute_verdict` took the last run only. Failing tests and collection errors are now unioned across runs, so a later green run can't mask an earlier added-test or suite failure.
- Interface requested/proposed (field-level types/example payload): `AgentRun.provider_mode` may now be `"none"` (field is free text; no contract change).
- Breaking change? migration/test impact: none. `test_unified_assessment` asserts `provider_mode == "none"` with 0 LLM calls for the functional Verify run.
- Action required by recipient: review the PR. Note: `KILL_SWITCH` has no `shared.errors` counterpart, so `_host_error(ErrorCode.KILL_SWITCH, …)` would raise ValueError; I didn't change it.
- Response-by milestone (not invented clock time): M7.
- Evidence: `uv run pytest -q security-agents/tests/test_agent_logic.py security-agents/tests/test_functional_verification_guards.py backend/tests/test_unified_assessment.py` → 71 passed. Root suite on main: 323 passed, 7 skipped. Frontend typecheck/lint/vitest (29) green.
- In-Reply-To (optional): `coordination/messages/20261017T081920Z-srihith-to-alan-hold-71-review-73.md`
