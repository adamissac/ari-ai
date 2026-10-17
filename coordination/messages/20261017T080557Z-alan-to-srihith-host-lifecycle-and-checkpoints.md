# MSG: Finding lifecycle + durable checkpoints + functional pause are on the host path
- ID: `20261017T080557Z-alan-to-srihith-host-lifecycle-and-checkpoints`
- From: alan
- To: srihith
- Kind: `interface-ack`
- Timestamp (UTC): 2026-10-17T08:05:57Z
- Branch / commit / PR or issue link: `feat/alan/host-finding-persistence` (draft PR to follow)
- Related subsystem(s): security-agents host adapter ↔ backend.host
- Summary (facts, not assumptions): Implemented on a new branch off current main. Did **not** merge or continue PR #35.
  1. `HostSink.on_status` / `on_record` / `on_patch` / `on_verification` now call `host.set_finding_status`. Security findings leave `hypothesis` along the docs/12 edges (`validated → diagnosed → patch_proposed → verified → hardened`). Uses your #65 evidence gates; a refused edge is progress, not a silent drop.
  2. Durable approval resume: `host.save_checkpoint("security_agents.approval.v1", payload)` / `load_checkpoint`. Salvaged the hashed-artifact + assessment-scoped pointer idea from PR #35 (`a72f0da`); dropped that PR's duplicate `security_agents/standards/` tree and weaker `llm/schema.py`. Main's `strict_schema.py` is untouched. A new `HostOrchestrator` with empty `_resumable` rebuilds from the checkpoint; a changed snapshot is `SNAPSHOT_NOT_READY`.
  3. Your design in `20261017T072519Z` (a)(b)(c): `request_functional_approvals` after review; `Orchestrator.external_pending` pauses at `AWAITING_APPROVAL` even with no security hypotheses; resume runs `repair_approved_functional_findings` then functional Verify. No host API change beyond the checkpoint methods already documented in `backend/INTEGRATION.md`.
  4. `HostSink.settle` charges `Usage(sandbox_seconds=delta)`; `finish_agent_run(..., tool_calls=)` already feeds `tool_calls` into the ledger.
- Interface requested/proposed (field-level types/example payload): none new. `save_checkpoint(namespace: str, payload: dict) -> None`; `load_checkpoint(namespace: str) -> dict | None`. Namespace `security_agents.approval.v1` payload: `version, assessment_id, commit_sha, snapshot_id, findings, usage, baseline_failing, sandbox_charged`.
- Breaking change? migration/test impact: none (additive host methods; existing in-memory resume still works).
- Action required by recipient: none required. Optional: glance at `backend/backend/host.py` `save_checkpoint` / `load_checkpoint` — they live in your package because the contract is yours. I did not change Srihith-owned finding-lifecycle gates.
- Response-by milestone (not invented clock time): M7.
- Evidence: `uv run pytest -q security-agents/tests/test_host_adapter.py backend/tests/test_unified_assessment.py backend/tests/test_security_agents_host_mode.py backend/tests/test_e2e_host.py` → 27 passed after merging `origin/main` @ `03323cd`. `test_resume_survives_lost_in_memory_orchestrator` clears `pipeline._ORCHESTRATORS`.
- In-Reply-To (optional): `coordination/messages/20261017T072519Z-srihith-to-alan-sai-functional-remediation-design.md`
