# MSG: Intelligence memory integrated; contract-owner ACK remains for #39

- ID: `20261017T043509Z-sarosh-to-all-intelligence-memory-integrated`
- From: sarosh
- To: srihith (contract owner); cc sai, alan, vihaan
- Kind: `integration-status` + `contract-ack-request`
- Timestamp (UTC): 2026-10-17T04:35:09Z
- Branch / commit / PR or issue link: `feat/sarosh/intelligence-memory`, PR #39, issue #38
- Related subsystem(s): shared / code-intelligence / backend / code-review / security-agents

## Status (facts, not assumptions)

- Recovered and continued the earlier Codex worktree; nothing was discarded.
- Fixed the backend CI failure: the latest-decision subquery now selects
  `expectation_id` before ordering by it. The new host test now passes canonical
  `AgentName` values.
- Merged `origin/main` through `dd9f8a9`; Sai's remediation/runtime changes and
  Alan's runtime files were preserved (only the isolated host adapter hook added).
- Implemented on the branch:
  1. `expectations(ref)` surfaces the latest authenticated decided status with a
     `human_input` EvidenceRef; rejected expectations are filtered by the security
     adapter. This satisfies Sai ask 1.
  2. `verified_regressions(ref)` returns canonical candidate proof. This satisfies
     Sai ask 2.
  3. Accepted independent Verify with all five unique checks enqueues a durable,
     deduplicated `register_verified_regression` job; replay is idempotent and
     exact-base-SHA candidate evidence is surfaced in context packs.
  4. Real backend hosts share one PostgreSQL intelligence service through a small
     `AssessmentHost.intelligence_service`/`attach_snapshot` hook; explicit
     directory/dev fixtures keep the labeled local fallback.

## Evidence on the merged tree

- backend/shared/monitoring/reviewer: **154 passed, 5 skipped**.
- code-intelligence/shared: **62 passed, 2 skipped**.
- code-review: **48 passed, 1 skipped**.
- security-agents: **344 passed, 11 skipped**.
- Focused memory/host tests: **7 passed**.
- Ruff/format on changed paths, strict mypy (root/code-intelligence/code-review),
  generated contract freshness (92 files, 0 changed) and 223-document link check passed.
- Skips: opt-in live provider, RL package/TypeScript compiler, sandbox-only tests.
  No live model, browser or deployment claim.

## Ask

Srihith: please ACK or counter additive schema 0.6.0 on #38/PR #39. Sai and Vihaan
already ACKed. The code is tested but will not land on main without your contract
ack. Flag any path overlap before merge; PR #39 remains draft until then.
