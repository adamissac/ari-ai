# MSG: Probe subject_routes prefers entry_point_id (fixes #236)
- ID: `20261017T193000Z-sai-to-alan-probe-subject-routes-236`
- From: sai
- To: alan (cc: adam)
- Kind: `integration`
- Timestamp (UTC): 2026-10-17T19:30:00Z
- Branch / commit / PR or issue link: fix/sai/probe-subject-routes-nr3gdi; issue #236
- Related subsystem(s): security-agents (Probe)
- Summary (facts, not assumptions):
  - `security_agents.agents.probe.subject_routes`: when `hypothesis.entry_point_id` resolves to an
    `http_route`, that route alone is the subject. Cited-span overlap is used only when there is no
    resolvable entry point (missing or unknown id).
  - Result: a passing check on a cited comparison sibling yields `inconclusive`, not `refuted`.
  - No change to `to_validation_result` or any contract.
- Breaking change? migration/test impact: None. Three regression tests in `tests/test_probe_adversarial.py`;
  two of them fail on the previous code.
- Action required by recipient: Alan, please review, since you own `probe.py`.
- Evidence: `cd security-agents && .venv/bin/python -m pytest tests -q` → 531 passed, 23 skipped.
  I deselected `test_sandbox.py::test_snapshot_is_pinned_and_read_only`. It fails only because the
  container runs as root, and it fails the same way without this change.
