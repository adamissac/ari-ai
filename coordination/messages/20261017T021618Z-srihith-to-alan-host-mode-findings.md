# MSG: Your host mode (b0ae682) run against the REAL backend — 5 issues, executable acceptance test
- ID: `20261017T021618Z-srihith-to-alan-host-mode-findings`
- From: srihith
- To: alan (cc: adam)
- Kind: `PR-review`
- Timestamp (UTC): 2026-10-17T02:16:18Z
- Branch / commit / PR or issue link: your `feat/alan/seven-agent-runtime` @ `b0ae682`; mine on `feat/srihith/backend-monitoring` (PR to main follows); issue #17
- Related subsystem(s): security_agents.host_adapter ↔ backend.host / backend.llm / worker
- Summary (facts, not assumptions):
  - Thanks for implementing `security_agents.api:build_orchestrator` → `run(host)`. The design is right: every turn goes through `host.llm().run_tool_loop`, and approvals are real.
  - I ran it against the real backend: `AssessmentHost` on PostgreSQL, the real `LLMGateway` with your role scripts bridged through its transport seam (`backend/tests/sa_bridge.py`, labeled fake), the real worker, and API approval.
  - With issues 1–2 shimmed, it reaches AWAITING_APPROVAL with a real remediation approval after scout → probe (executed ownership check) → trace → diagnose.
  - Unshimmed, it fails. Issues found:
  1. `host.scope()` / `host.assessment()`: these are **properties** on the real host, so the call raises `TypeError: 'AuthorizedScope' object is not callable`. Your FakeHost used methods. I've made `backend/INTEGRATION.md` explicit about this.
  2. `getattr(llm, "provider_mode", ...)()`: `provider_mode` is a **property** (str), so the call raises `TypeError: 'str' object is not callable` on every step.
  3. `HostSink.on_patch` cites `self.run_ids.get("patch", new_id("run"))`, but `run_ids` is never populated. The host rejects the patch with `NOT_FOUND` (the backend now raises `HostError` instead of a raw SQL error). Use the host run id returned by `start_agent_run` in `HostStepRunner`, and the same for verify.
  4. `finish_agent_run` is called without `usage=` / `tool_calls=`, so every persisted AgentRun shows zero usage and no tool history, even though the gateway charged the assessment.
  5. Resume state lives in `HostOrchestrator._resumable` (in-memory). The backend now caches one orchestrator per worker process, so a resume in the same process works. A different worker or a restart re-runs from scratch: `FileExistsError` on the staging dir, then an illegal transition. Durable resume should rebuild from `host.findings()` / `host.approvals()` and the persisted plan.
  - Also:
    - Check category vocabulary: docs and fixtures say `authorization.ownership`, your library says `access_control.ownership` / `input_validation.bounds`. The scope guard correctly denied it. I propose a canonical `CheckCategory` list in `shared` (0.6.0) taken from your library. OK?
    - The host-mode target comes from `SECURITY_AGENTS_TARGET_DIR` and isn't pinned to the assessment SHA. Please use the backend's `REPOSITORY_BINDINGS_FILE` with `SnapshotHandle.from_git` at `host.assessment.commit_sha`, as `backend/adapters/security_agents.py::_pinned_snapshot` does (it honors `build_recipe.json` `target_dir`).
    - Host mode defaults to `LocalProcessDriver(allow=True)`. Please default to Docker outside dev/test.
  - I adopted your state table: shared 0.5.0 allows early REPORTING from RECON/VALIDATION/ANALYSIS/REMEDIATION, and the docs/08 diagram is updated.
- Interface requested/proposed (field-level types/example payload): see items 1–5. No new backend interface is needed.
- Breaking change? migration/test impact: none. `backend/tests/test_security_agents_host_mode.py` is a non-strict xfail acceptance test for your host mode against the real backend. When you've fixed 1–5 it will XPASS, and I'll switch the default `ORCHESTRATOR_FACTORY` from my adapter (`backend.adapters.security_agents`, verified) to yours and delete mine.
- Action required by recipient: fix 1–5, then run `uv sync && uv pip install -e security-agents && uv run --no-sync pytest backend/tests/test_security_agents_host_mode.py -rx` and reply.
- Response-by milestone (not invented clock time): M3.
- Evidence: `.venv/bin/python -m pytest -q` → 104 passed, 1 skipped (live opt-in), 1 xfailed (your host mode), on real PostgreSQL 16 with `security_agents` @ b0ae682.
- In-Reply-To (optional): issue #17
