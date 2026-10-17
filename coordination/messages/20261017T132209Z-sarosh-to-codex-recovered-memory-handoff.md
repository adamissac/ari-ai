# MSG: Codex resume handoff — recovered intelligence-memory work is merged; start from main

- ID: `20261017T132209Z-sarosh-to-codex-recovered-memory-handoff`
- From: sarosh
- To: codex (resuming Sarosh's implementation lane); cc srihith, sai, alan, vihaan
- Kind: `handoff`
- Timestamp (UTC): 2026-10-17T13:22:09Z
- Branch / commit / PR or issue link: worktree `/tmp/hackatl-sarosh-memory`; PR #39 merged as `2ab5584`; issue #38 closed; current `origin/main` at `39186cb`
- Related subsystem(s): shared / code-intelligence / backend / code-review / security-agents

## Where we started

The previous Codex session stopped with uncommitted work in `/tmp/hackatl-sarosh-memory`
on `feat/sarosh/intelligence-memory` at `ca30d4d`:

- 7 modified files and 2 untracked files
- 2 tests passing, 1 failing in `backend/tests/test_intelligence_memory_api.py`
- the failing test passed string agent names to `AssessmentHost.start_agent_run`
  (which expects `AgentName`); the committed backend CI failure was different:
  `PostgresMemoryStore.decisions` ordered by `latest.c.expectation_id` without
  selecting `expectation_id` in the latest-revision subquery.

Nothing was restarted from scratch and no prior change was discarded.

## What was fixed

1. `backend/backend/intelligence_memory.py`: added
   `expectation_decisions.c.expectation_id` to the window-function subquery so
   latest-decision reads work in PostgreSQL.
2. `backend/tests/test_intelligence_memory_api.py`: use canonical
   `shared.assessment.AgentName.patch` / `.verify`.
3. `code-review/tests/test_host_integration.py`: the independent Verify test
   double now supplies the fifth canonical check
   (`original_check_now_fails_to_reproduce`) required by the trusted host gate.
4. `security-agents/security_agents/intel/host_service.py`: directory/dev
   snapshots return the labeled local fallback instead of raising
   `SNAPSHOT_NOT_READY`; git-pinned hosted snapshots use the shared service.
5. `backend/backend/intelligence_jobs.py`: missing canonical snapshot is a
   retryable job failure, not a permanent one, so a later snapshot attachment
   can still complete the regression join.

## What was implemented

- Exact-snapshot `ExpectationDecisionRequest` / `ExpectationDecision` and
  `VerifiedRegression` contracts (schema 0.6.0, additive).
- Append-only SQLite and PostgreSQL memory stores beside immutable index payloads;
  authenticated backend routes for decision, history and regression reads;
  optimistic revision control; `human_input` evidence in expectations/context.
- Durable, deduplicated accepted-Verify -> `register_verified_regression` outbox
  job. Registration requires all five unique checks, a separate producing Verify
  run, executed test/sandbox evidence and the exact patch base SHA. Replay is
  idempotent.
- `AssessmentHost.intelligence_service()` and `attach_snapshot()` plus the security
  `shared_host_intel` adapter so real hosted assessments use the one PostgreSQL
  intelligence service. Explicit fake/directory fixtures keep the local fallback.
- Reviewer shared-intelligence hook in `code_review/api._runner`.
- Documentation/status/handoff updates and the hold communication
  `20261017T044521Z-sarosh-to-all-pr39-hold-for-ack.md`.

Key files:

- `shared/shared/intelligence_memory.py`
- `code-intelligence/code_intelligence/memory.py`
- `code-intelligence/code_intelligence/api.py`
- `backend/backend/intelligence_memory.py`
- `backend/backend/intelligence_jobs.py`
- `backend/backend/api/intelligence.py`
- `backend/backend/migrations/versions/0005_intelligence_memory.py` / `0006_merge_memory_and_incidents.py`
- `backend/backend/host.py`
- `security-agents/security_agents/intel/host_service.py`
- `security-agents/security_agents/intel/code_intelligence_adapter.py`
- `code-review/code_review/api.py`

## Commits and merge

- `b13bd82` feat(intel): wire durable verified-regression outbox and shared hosted intel
- `de8e3a3` merge origin/main into the branch (preserved Sai's remediation/runtime work)
- `4b9fc39` test(intel): finish memory integration handoff and shared host fallback
- `b73caab` docs(coordination): record PR 39 merge hold pending contract-owner ACK
- PR #39 merged by Adam at 2026-10-17T05:30:31Z as `2ab5584`
- Issue #38 closed as COMPLETED
- No commits from this lane are left unmerged.

## Current state

- Recovered worktree fast-forwarded to `origin/main` at `39186cb`; working tree clean.
- `main` now also contains standards/incidents (schema 0.10.0) and migration 0006,
  which merges the intelligence-memory and incident migration revisions.
- Our memory files remain present and the consumer paths still work.
- Sai's `20261017T055414Z-sai-to-sarosh-decisions-consumer-confirmed.md` confirms the
  real service decisions drive reviewer claims (asks 1 and 2 satisfied).
- No action is pending on PR #39 or issue #38.

## Verification executed

On the merged PR tree before merge:

- backend/shared/monitoring/reviewer **154 passed, 5 skipped**
- code-intelligence/shared **62 passed, 2 skipped**
- code-review **48 passed, 1 skipped**
- security-agents **344 passed, 11 skipped**
- focused memory/host tests **7 passed**
- Ruff/format on changed paths, strict mypy (root/code-intelligence/code-review),
  contract freshness and link checks passed
- PR CI: all seven checks passed

After fast-forwarding to current `main` and running `uv sync --frozen`:

- `backend/tests/test_intelligence_memory_api.py`,
  `code-intelligence/tests/test_memory.py`,
  `shared/tests/test_intelligence_memory_contracts.py` -> **8 passed**
- `backend/tests/test_m7_push_to_regression.py`,
  `backend/tests/test_security_agents_host_mode.py`,
  `backend/tests/test_unified_assessment.py`,
  `code-review/tests/test_intel_integration.py`,
  `code-review/tests/test_host_integration.py` -> **11 passed**
- `uv sync --frozen` installed the current main workspace including `standards`.

Skips above are opt-in live provider, RL package/TypeScript compiler and
sandbox-only tests. No live-model, browser, target-probe or deployment claim.

## Next actions for the resuming Codex

1. `git fetch origin --prune`; start new work from current `origin/main`, not from the
   old merged branch. Do not redo #39 or rewrite merged history.
2. Read the latest `coordination/messages/`, `coordination/status/SAROSH.md`,
   `coordination/MILESTONES.md` and open PRs before choosing work.
3. Run `uv sync --frozen` after pulling if the workspace changed (it now includes
   `standards`). Use the commands above as smoke checks.
4. Pick up only genuinely remaining work from the task board/PRs. Do not claim the
   UI, live provider, Docker sandbox or full M7 runtime from this lane's evidence.
5. Use a new `feat/sarosh/<scope>` or `docs/sarosh/<scope>` branch; never push
   directly to `main`. Open a PR with executed test evidence.

## Warnings

- Do not re-run old `0005` assumptions blindly: current main uses
  `0005_incident_handling` plus `0005_intelligence_memory` and a merge revision `0006`.
- Decisions/regressions are exact-SHA candidate evidence. Never carry a confirmation
  or regression pass to another commit without re-validation.
- `rejected` expectations must not support a reviewer/agent claim.
- Regression evidence does not mean the patch was merged or currently passes.

## Evidence pointers

- Recovery/continuation message: `coordination/messages/20261017T043509Z-sarosh-to-all-intelligence-memory-integrated.md`
- Merge-hold message: `coordination/messages/20261017T044521Z-sarosh-to-all-pr39-hold-for-ack.md`
- Consumer confirmation: `coordination/messages/20261017T055414Z-sai-to-sarosh-decisions-consumer-confirmed.md`
- Status: `coordination/status/SAROSH.md`
- Product docs: `code-intelligence/README.md`, `docs/11_SHARED_CONTEXT_AND_MEMORY.md`
