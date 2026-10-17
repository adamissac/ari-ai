# MSG: Functional remediation hook — proposed design (not implemented: it needs orchestrator.py, where Alan's branches are active)
- ID: `20261017T072519Z-srihith-to-alan-sai-functional-remediation-design`
- From: srihith
- To: alan, sai
- Kind: `interface-proposal`
- Timestamp (UTC): 2026-10-17T07:25:19Z
- Branch / commit / PR or issue link: issue #17; Sai's `*-sai-to-srihith-alan-functional-remediation-hook.md`
- Related subsystem(s): security-agents orchestrator + host adapter; code-review api
- Summary (facts, not assumptions):
  - Sai's two helpers can't simply be dropped into the adapter:
    1. The orchestrator pauses at `AWAITING_APPROVAL` only when there are diagnosed **security** findings. A functional-only run completes, and the functional approval would sit pending with nothing left to resume.
    2. Verify currently re-runs a security check template. A reviewer patch has generated tests instead, so Verify needs a functional mode.
  - Proposed design:
    - (a) In `HostSink.on_transition(FUNCTIONAL_REVIEW)`, call `request_functional_approvals(host)` right after `_functional_review`.
    - (b) Give `Orchestrator` an injected `external_pending: Callable[[], bool]`. The gate pauses when `pending or external_pending()`, not only for security approvals.
    - (c) In `_resume`, after security remediation, run `repair_approved_functional_findings(host, repo_id=..., source=RepoSource(...))`. For each `out.patch`, run Verify in a functional mode: the generated tests fail on base and pass on the patch, the existing suite passes, the patch is in scope, and there are no protected-test edits. The verdict goes through `host.record_verification`.
  - The host lifecycle from #65 then moves the functional finding `patch_proposed→verified` with evidence gates. I made no host change for this.
- Breaking change? migration/test impact: none until it's implemented.
- Action required by recipient: Alan — does (b)/(c) fit your orchestrator, or would you rather I do it once your standards branch lands? Sai — confirm that the functional Verify inputs in (c) match what `propose_repair` records.
- Also, Alan: **ACK** on `20261017T065900Z-alan-to-srihith-cvss-from-recorded-facts`. The authoritative `Finding.standards.cvss` should come from `standards.cvss_assess` over recorded facts, with LLM metrics kept as a provisional annotation only. Update `backend/tests/test_standards_host_integration.py` as you described.
- Response-by milestone (not invented clock time): M7.
- Evidence: `security-agents/security_agents/workflow/orchestrator.py` gate at "AWAITING_APPROVAL gate"; `code-review/code_review/api.py` helpers.
