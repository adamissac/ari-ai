# MSG: PR #39 is green and waiting on contract-owner ACK — what each owner needs to do

- ID: `20261017T044521Z-sarosh-to-all-pr39-hold-for-ack`
- From: sarosh
- To: srihith (contract owner); cc sai, alan, vihaan, adam
- Kind: `handoff` + `blocker` + `contract-ack-request`
- Timestamp (UTC): 2026-10-17T04:45:21Z
- Branch / commit / PR or issue link: `feat/sarosh/intelligence-memory` at `4b9fc39`; PR #39; issue #38
- Related subsystem(s): shared / code-intelligence / backend / code-review / security-agents

## Decision

We are **waiting to push to `main`**. The branch is complete and CI is green, but
additive schema **0.6.0** is still unreviewed by the contract owner. We will merge
through PR #39 after Srihith ACKs or counters. We will **not** push directly to
`main`; that would bypass the contract review and CI trail.

## Current state (facts)

- PR #39 head `4b9fc39`, mergeable; all seven GitHub checks pass (backend,
  code-intelligence, code-review, security-agents, backend-image, links, gitleaks).
- Local merged-tree evidence: backend/shared/monitoring/reviewer **154 passed,
  5 skipped**; code-intelligence/shared **62 passed, 2 skipped**; code-review
  **48 passed, 1 skipped**; security-agents **344 passed, 11 skipped**; focused
  memory/host tests **7 passed**.
- Skips: opt-in live provider, RL package/TypeScript compiler, sandbox-only tests.
  No live-model, browser, target-probe or deployment claim.
- Implemented: exact-snapshot `ExpectationDecision` / `ExpectationDecisionRequest` /
  `VerifiedRegression`; authenticated backend decision/history/regression routes;
  append-only PostgreSQL/SQLite memory beside immutable index payloads; decided
  expectations in context packs with `human_input` evidence; durable deduplicated
  accepted-Verify → regression outbox; shared hosted intelligence adapter.

## What each owner needs to do

### Srihith — only merge-blocking action

ACK or counter additive schema 0.6.0 on issue #38 / PR #39. Please confirm:

- `ExpectationDecisionRequest` / `ExpectationDecision` and `VerifiedRegression`
  fields are acceptable as implemented (existing entity fields unchanged);
- append-only storage beside, not inside, immutable index payloads is acceptable;
- backend-authenticated actor + optimistic `expected_revision` is acceptable;
- candidate-regression evidence is scoped to an exact base SHA and is never a
  merge/current-SHA claim.

If you need changes, comment on #39 or send an immutable counter-message. If you
ACK, I will merge PR #39 through GitHub.

### Alan — integration confirmation (not merge-blocking)

The security host adapter now uses the shared PostgreSQL intelligence service for
real hosted assessments via `shared_host_intel`, with `AssessmentHost.attach_snapshot`
and `intelligence_service`. Explicit directory/dev fixtures keep the labeled local
fallback. Please flag immediately if this overlaps your active runtime work; no
prompts, tool schemas, workflow stages or sandbox driver were changed.

### Sai — consumer confirmation (not merge-blocking)

Sai's asks are implemented: `expectations(ref)` returns the latest decided status
with `human_input` evidence, and `verified_regressions(ref)` is public. The review
hook only uses the shared service when the host exposes `intelligence_service`; the
existing standalone/fake path is unchanged. The code-review test double now supplies
the fifth canonical Verify check required by the trusted host boundary.

### Vihaan — UI follow-up (not merge-blocking)

After #39 lands, wire the authenticated confirm/conflicting/reject controls with a
required reason and `expected_revision` (show 409 as a conflict, never silently
retry) and list verified regressions on the finding page. No frontend changes were
made by me.

### Adam — schema ordering awareness (no action)

Alan's standards branch takes 0.7.0; PR #39 keeps 0.6.0. Whichever merges second
rebases `shared/shared/__init__.py` and regenerates contracts.

## Next action

Srihith ACK/counter → Sarosh merges PR #39 → move the 0.6.0 entry out of the draft
hold. Until then the branch and CI result stay available at `4b9fc39`.
