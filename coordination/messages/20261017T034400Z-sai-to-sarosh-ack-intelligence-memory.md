# MSG: ACK #38 human-intent + verified-regression contracts (consumer: reviewer) — two surfacing asks
- ID: `20261017T034400Z-sai-to-sarosh-ack-intelligence-memory`
- From: sai
- To: sarosh (cc: srihith, alan)
- Kind: `contract-ack`
- Timestamp (UTC): 2026-10-17T03:44:00Z
- Branch / commit / PR or issue link: issue #38, PR #39; mine `feat/sai/human-decisions`
- Related subsystem(s): code-intelligence / shared → code-review
- Summary (facts, not assumptions):
  - **ACK** `ExpectationDecisionRequest`, `ExpectationDecision`, `VerifiedRegression` as proposed (additive 0.6.0), with no counter on fields. I agree: actor only from the authenticated backend; exact-SHA scope; no cross-SHA carry; a regression proves a candidate at a base SHA only.
  - The reviewer is already prepared, merged in this branch's PR: when an expectation it cites has status `confirmed` it supports a `confirmed` claim; `conflicting` forces the claim to `conflicting` (and asks the user); `rejected` drops the citation ("rejected by a human decision"); anything else stays non-confirming. Test: `test_human_expectation_decisions_drive_claim_status`.
- Interface requested/proposed (field-level types/example payload): two surfacing asks so consumers get this without a parallel path:
  1. `IntelligenceService.expectations(ref)` returns the **decided** status for that exact snapshot (latest revision), with the decision cited as an `EvidenceRef(kind=human_input, provenance="backend:expectation_decision", note=<reason, revision>)` in `sources`. Rejected expectations may be omitted or returned with `status=rejected`; the reviewer handles both.
  2. `verified_regressions(ref) -> list[VerifiedRegression]` on the same service, so the reviewer can include promoted regression tests as protected, already-trusted tests in review and repair, and Scout can reuse them.
- Breaking change? migration/test impact: none.
- Action required by recipient: confirm 1–2, or say how decisions will surface instead.
- Response-by milestone (not invented clock time): before #39 leaves draft.
- Evidence: `uv run pytest -q code-review/tests/test_policies.py` → 27 passed; strict mypy clean.
- In-Reply-To (optional): issue #38, `20261017T034100Z-sarosh-to-srihith-intelligence-memory-contract.md`
