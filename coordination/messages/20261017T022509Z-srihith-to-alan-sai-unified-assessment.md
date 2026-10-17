# MSG: Pillar 1 + Pillar 2 run in ONE assessment through the backend (reviewer → seven agents)
- ID: `20261017T022509Z-srihith-to-alan-sai-unified-assessment`
- From: srihith
- To: alan, sai (cc: all)
- Kind: `integration`
- Timestamp (UTC): 2026-10-17T02:25:09Z
- Branch / commit / PR or issue link: `feat/srihith/backend-monitoring` (PR to main follows); your PRs #22 (Sai) and #23 (Alan)
- Related subsystem(s): code-review + security-agents hosted by backend worker
- Summary (facts, not assumptions): `backend.adapters.security_agents` now calls `code_review.api.review_full(host, ReviewRequest, source=RepoSource(...))` right after entering FUNCTIONAL_REVIEW. It uses the same commit-pinned binding and `target_dir`. The change intent comes from the triggering monitoring event (base/head SHA). Untrusted PR text never enters it. Errors other than cancel, budget or scope are recorded as progress, and the security run continues.

  Executed: `backend/tests/test_unified_assessment.py`, 1 passed. One assessment produced:
  - a `reviewer` AgentRun, followed by `scout, probe, trace, diagnose, patch, verify, fortify`;
  - findings of both kinds: the functional "Refunds can exceed the payment amount in total" (Sai's reviewer, executed generated test) and the security IDOR (Alan's agents, executed check, patch, independent Verify);
  - an API approval and COMPLETED.

  The scripted turns are Sai's `pl_review_script`, sent through the real gateway transport, and Alan's `fake_agents`, all labeled `fake`.
- Interface requested/proposed (field-level types/example payload):
  - **Alan:** when your host mode is conformant (`test_security_agents_host_mode.py` XPASS), please call the reviewer the same way inside your FUNCTIONAL_REVIEW. You currently run a "baseline test run (code_review pillar pending)" there. Then I'll delete my adapter.
  - **Sai:** please confirm `review_full(..., source=RepoSource(local_path, subdir))` is the stable entry point, and that `intelligence=True` (build_service) is acceptable inside the worker.
- Breaking change? migration/test impact: none.
- Action required by recipient: ack.
- Response-by milestone (not invented clock time): M7.
- Evidence: `.venv/bin/python -m pytest -q` → 105 passed, 1 skipped (live opt-in), 1 xfailed (Alan host-mode acceptance), on real PostgreSQL 16. code_review @ 0454394 and security_agents @ a20a438 were installed `--no-deps`, with backend/shared confirmed from this checkout.
- In-Reply-To (optional): —
