# MSG: M7 chain is one automated test now; M4/M7 evidence recorded; monitoring-budget finding
- ID: `20261017T093205Z-srihith-to-all-m7-chain-automated`
- From: srihith
- To: all
- Kind: `integration`
- Timestamp (UTC): 2026-10-17T09:32:05Z
- Branch / commit / PR or issue link: `test/srihith/m7-push-to-regression`; earlier #84 / #85 merged
- Related subsystem(s): backend, monitoring, security-agents, code-review, intelligence memory
- Summary (facts, not assumptions):
  - `backend/tests/test_m7_push_to_regression.py` drives a signed push through to verified regressions, end to end. The full chain is listed in MILESTONES (M7 evidence). M4 and M7 are ticked there, with commands, counts and limitations.
  - **Finding (product decision, not changed):** the default `monitoring_policy.monitoring_budget` (150k tokens / $3) ends a full push-triggered run in `BUDGET_EXHAUSTED` at remediation, even with scripted turns. Options:
    - (a) raise the default to the manual 400k / $10;
    - (b) keep it and document that owners must size it;
    - (c) give the remediation phase its own budget.
    The test uses (b) via `PATCH /projects/{id}`.
  - Also merged: #84 (Verify masking, honest `none` label, synthetic snapshot ref, ErrorCode). In #85 I merged main into Adam's branch: it kept the error-code guard test, and I added the suite-side no-masking rule.
- Breaking change? migration/test impact: none. The `unified` fixture now also yields `repo_path`.
- Action required by recipient: Adam / product owner: choose (a), (b) or (c) for the monitoring budget.
- Evidence: M7 test 1 passed; root suite 325 passed; the M4 gate set 34 passed.
