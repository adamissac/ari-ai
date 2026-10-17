# MSG: Changes I made to security-agents while you were away (merged in #36)
- ID: `20261017T032547Z-srihith-to-alan-changes-made-while-away`
- From: srihith
- To: alan (cc: all)
- Kind: `handoff`
- Timestamp (UTC): 2026-10-17T03:25:47Z
- Branch / commit / PR or issue link: PR #36 → main @ `ea36e47`; issue #17
- Related subsystem(s): security-agents (your path), backend
- Summary (facts, not assumptions): Our user asked me to fix blockers in teammates' code directly while you're unavailable. Everything below is in your path. Please review when you're back; revert or rework anything you disagree with.
  1. **`tools/strict_schema.py` (new) + `tools/registry.py`.** Every agent's tool set was rejected live with HTTP 400 (integer `minimum`; `additionalProperties: object`). Unsupported strict-mode keywords are now stripped from the schema that gets *sent*; your Pydantic `args_model` still validates inputs. Tools with free-form map arguments go non-strict. Verified with `messages.count_tokens` (free): 7/7 accepted. `tests/test_strict_schema.py` is new, with the live test opt-in. I changed `tests/test_tool_registry.py::test_tool_schemas_are_provider_valid` to expect non-strict only for free-form maps.
  2. **`workflow/orchestrator.py` `_run_scout`.** A failed Scout now raises `PlatformError` with its error code. It no longer returns `[]`, which used to show as "no hypotheses" → COMPLETED.
  3. **`host_adapter.py`:**
     - host property/method shapes are accepted via `_val`, and `provider_mode` is read as a property;
     - `HostStepRunner` shares the real host run ids with `HostSink`, so patches never cite invented ids;
     - `finish_agent_run` receives the gateway's `usage`/`tool_calls`;
     - a lost resume raises a clear CONFLICT_STATE;
     - `_build_intel` uses a git-pinned checkout from `REPOSITORY_BINDINGS_FILE` at `assessment.commit_sha` (honoring `target_dir`). `SECURITY_AGENTS_TARGET_DIR` remains as a dev fallback. **`labels.yaml` is no longer read implicitly** because it is the answer key; `labels_path`/`SECURITY_AGENTS_LABELS` remain as explicit dev overrides;
     - `_driver()` uses Docker by default, and local-dev only in development/test;
     - `HostSink.on_transition` runs Sai's `review_assessment` at FUNCTIONAL_REVIEW, falling back to `review_full` without an indexed snapshot.

     `tests/test_host_adapter.py`: the missing-target error is now SNAPSHOT_NOT_READY.
  4. **Backend.** `ORCHESTRATOR_FACTORY` now defaults to your `security_agents.api:build_orchestrator`. I removed my duplicate `backend/adapters/`.
  5. **Workspace and CI.** `security-agents` is a uv workspace member, and a new `.github/workflows/security-agents.yml` runs your suite.
- Interface requested/proposed (field-level types/example payload): none new.
- Breaking change? migration/test impact: Host mode needs a repo binding, or `SECURITY_AGENTS_TARGET_DIR` in dev. Labels are no longer auto-loaded.
- Action required by recipient: Review #36's diff under `security-agents/`. Open item: durable resume across workers/restarts (rebuild from host records).
- Response-by milestone (not invented clock time): when back.
- Evidence:
  - your suite: 344 passed, 11 skipped;
  - root suite: 148 passed, 4 skipped;
  - `backend/tests/test_unified_assessment.py` (host mode): reviewer + 7 agents through ONE gateway → approval → resume → patch → accepted Verify;
  - CI on #36: all 6 workflows green.
- In-Reply-To (optional): issue #17
