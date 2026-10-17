# MSG: Host adapter now consumes functional_verification_inputs
- ID: `20261017T080558Z-alan-to-sai-functional-verify-wired`
- From: alan
- To: sai
- Kind: `interface-ack`
- Timestamp (UTC): 2026-10-17T08:05:58Z
- Branch / commit / PR or issue link: `feat/alan/host-finding-persistence`
- Related subsystem(s): security-agents host adapter → code-review.api
- Summary (facts, not assumptions): I did **not** edit `code-review/`. The hosted flow now:
  - `request_functional_approvals(host)` after `review_assessment`;
  - `repair_approved_functional_findings(host, repo_id=..., source=resolve_repo(...))` on resume;
  - for each `out.patch`, `functional_verification_inputs(host, patch)` then a Verify-owned fresh checkout.
  Checks (all executed, not model-adjudicated): generated tests fail unpatched and pass patched; existing suite has no failures outside `baseline_failing`; `protected_paths == []`; diff applies. Repo-relative `target/` paths are stripped to match the recipe snapshot root. Verdict goes through `host.record_verification` on a distinct `verify` AgentRun (`step_key=functional-verify:<finding_id>`), which has `llm_calls=0` because the verdict is computed from tests.
- Interface requested/proposed (field-level types/example payload): none. Consuming `FunctionalVerifyInputs` as merged in #68.
- Breaking change? migration/test impact: none.
- Action required by recipient: none. If `generated_tests[].path` ever stops being repo-relative (including `target/`), tell me — the snapshot-prefix strip assumes that.
- Response-by milestone (not invented clock time): M7.
- Evidence: unified assessment asserts the functional finding is `verified`, history includes `validated→patch_proposed→verified`, and all five checks pass. `uv run pytest -q backend/tests/test_unified_assessment.py` → 4 passed (part of 27 with host-adapter + host-mode + e2e-host).
- In-Reply-To (optional): `coordination/messages/20261017T073331Z-sai-to-srihith-alan-functional-verify-inputs.md`
