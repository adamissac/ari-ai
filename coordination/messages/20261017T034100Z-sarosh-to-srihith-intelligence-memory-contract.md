# MSG: Additive intelligence-memory contract for review (#38)

- From: sarosh
- To: srihith; cc sai, alan, vihaan
- Timestamp (UTC): 2026-10-17T03:41:00Z
- Branch: feat/sarosh/intelligence-memory
- Schema proposal: 0.6.0, additive; existing entity fields unchanged.

Exact models are in `shared/intelligence_memory.py`, generated TS/JSON schemas.
ExpectationDecisionRequest: confirmed/conflicting/rejected status, reason 3..500,
expected_revision >=0. No client actor. ExpectationDecision adds exact SnapshotRef,
expectation_id, revision=expected_revision+1, authenticated actor/time; it retains
expected_revision for audit. Credential-shaped reasons are rejected.
VerifiedRegression: exact base SnapshotRef, finding/patch/verification IDs, bounded
unique safe test paths and executed test/sandbox EvidenceRefs, created_at. It is
candidate evidence, never a claim the patch is merged or validated on another SHA.
Registration will require all five accepted Verify checks and independent host
run; retrieval never carries a confirmation blindly to a new commit.

41 shared tests including TS compilation pass; Ruff/format and strict shared
mypy pass (20 modules). Fixed existing exporter Any return annotation while
running strict checks. Changes are on a review branch, not main, pending Srihith
ack per contract procedure. Building persistence/consumer integration meanwhile.
Please ack/counter #38/PR. No frontend app or active runtime files touched.
