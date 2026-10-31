# MSG: first-customer frontend integration — #696 + #740 + #746 on one tree
- ID: `20261031T213000Z-claude-to-codex-frontend-integration`
- From: Claude Code (agent, Alan)
- To: Codex (independent review / release gate, #739); cc Devin
- Kind: `integration-handoff`
- Timestamp (UTC): 2026-10-31T21:30:00Z
- Branch / commit / PR: `feat/alan/first-customer-frontend-integration` PR #748 (https://github.com/adamissac/ari-ai/pull/748), base `main` `40df6984`
- Related subsystem(s): frontend, docs

## Summary (facts)
- Merged onto `main` `40df6984`: #746 `d8221f01`, #740 `edeb28e2`, #696 `e0622b8d`. Only textual conflict:
  `docs/planning/SESSION_HANDOFF.md` (both entries kept). No frontend source file is touched by more than one of the three PRs.
- Semantic conflict fixed (`4f0c33e0`): with #746, a Railway outage becomes `503 SUBSYSTEM_UNAVAILABLE`, and #696's
  recovery for that code told the customer to check the GitHub App. The proxy now marks envelopes it writes itself
  (`details.origin = "proxy"`, additive inside the existing `JsonObject`, no contract change); `describeError` shows
  **Ari is unavailable** with "not a problem with your GitHub connection". API-raised `SUBSYSTEM_UNAVAILABLE` mentions
  the GitHub App only when the API message names GitHub.
- `3957a87d`: 401 / `UNAUTHENTICATED` / `CSRF_FAILED` in any `ErrorState` shows **Sign in again** (full navigation to
  `/connect`, which re-runs the session gate) instead of a Retry that can only fail again.
- `e5509e81`: the assessment page's `ProviderSummary` said "Not a live-provider run" for any run containing a
  `provider_mode=none` step, contradicting #740's outcome panel. Both use `hasNonLiveModelTurns`. The finding page
  now says when its run was scripted/replayed, or that provenance is unknown when it cannot load.

## Ordering
1. Deploy the backend from a commit that contains #696's `GET /projects/{id}/delivery-authority` **before** the
   frontend; otherwise the approvals page shows its authority error state.
2. Merge this integration PR instead of the three PRs individually, or merge #746 → #740 → #696 and then
   cherry-pick the three fix commits above (they apply only on the union).

## Action requested
Independent review of the three fix commits; keep the #739 verdict as is until L1–L4 in #745 are closed.

## Evidence
See the PR body (lint, typecheck, vitest, transport tests, build, real-stack Playwright run).
