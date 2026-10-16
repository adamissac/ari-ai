# 06 — Code review and repair

Status: **specified**. Directory: `code-review/`.

## Purpose

Answer *"does the software work the way it is supposed to?"* by checking code
against behavioral expectations, proving problems with executable tests, and
proposing candidate repairs that are verified by execution.

## Inputs

- `Snapshot` + `BehavioralExpectation`s from code-intelligence.
- Review target: whole snapshot, a diff (`base..head`), or a selected subject.
- `ContextPack`s requested from the retriever.
- A sandbox for running the target's test suite (via `security-agents`' sandbox
  driver, shared tool registry).

## Outputs

- `Finding` with `kind: functional`, status lifecycle shared with security
  findings ([12](12_DATA_MODELS_AND_CONTRACTS.md)).
- `GeneratedTest` (file path, code, expectation it encodes) and `TestRun`.
- `PatchCandidate` (unified diff in artifact store, worktree ref, test results).

## Review pipeline

1. **Select scope** — for a diff, impacted symbols from `affected_by_diff`; for a
   full review, entry points ranked by number of expectations.
2. **Check expectations** — for each (subject, expectation) pair, the LLM reviewer
   receives a context pack and must return a structured verdict:
   `consistent | violated | unclear`, with cited spans and a proposed test.
   `violated` without cited spans is rejected by schema validation.
3. **Prove** — generate a behavioral test that should pass if the expectation
   holds. Run it in a sandbox against the snapshot. Outcomes:
   - test fails for the reason predicted → Finding `validated` with TestRun evidence;
   - test passes → verdict downgraded, Finding `refuted` (kept for audit);
   - test errors (harness problem) → retry once with error context, then `inconclusive`.
4. **Repair (on request/approval)** — generate a minimal diff in an isolated git
   worktree; run the generated test + existing suite; produce a `PatchCandidate`.
5. **Hand to Verify** — functional repairs use the same Verify agent as security
   patches ([agents/INDEPENDENT_VERIFY](agents/INDEPENDENT_VERIFY.md)).

## Repair rules

- Minimal diff; no unrelated refactors; no edits to tests that encode confirmed
  expectations (editing a test to pass is an automatic rejection by Verify).
- Worktrees live under `.worktrees/<patch_id>` in the worker workspace (git-ignored),
  are never pushed automatically, and are deleted after the artifact is stored.
- A repair never touches dependency lockfiles unless the root cause is a
  dependency; then it is flagged for human review.

## Relationship to the security agents

Code review is P1; Patch/Diagnose are P2. They share: the Finding model, the
worktree + sandbox tooling, and Verify. They differ in trigger and evidence type:
code review proves with behavioral tests; Probe proves with non-destructive
security checks. A single Finding can be enriched by both (e.g. an authorization
expectation violation found by review and confirmed by Probe).

## Quality bar

The reviewer is measured by precision of `validated` findings on labeled
fixtures (`examples/`, [research/EVALUATION_DATASETS](research/EVALUATION_DATASETS.md)).
We never report LLM "violated" verdicts that lack an executed failing test as
findings — they appear only as `hypothesis`.

## Public interface (planned `code_review/api.py`)

| Function | Purpose |
|---|---|
| `review(snapshot_id, target: ReviewTarget, budget) -> list[FindingId]` | Run review job |
| `generate_tests(expectation_ids) -> list[GeneratedTest]` | Test generation |
| `propose_repair(finding_id, approval_id) -> PatchCandidateId` | Repair job (requires approval) |
