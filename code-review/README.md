# code-review/

> **What exists: nothing yet (Phase 0).** Spec: [docs/06](../docs/06_CODE_REVIEW_AND_REPAIR.md).

## Purpose
Pillar 1's judgment: does the code behave as its expectations say? Prove
problems with executed behavioral tests and propose candidate repairs.

## Responsibilities
- Review subjects against expectations with structured, citation-backed verdicts.
- Generate behavioral tests; run them in sandboxes; turn failing tests into
  validated functional findings.
- Produce minimal candidate repairs in isolated worktrees, then hand them to
  Verify.

**Must not:** re-index repos, run code outside the shared sandbox driver, report
unexecuted "violations" as findings, edit tests that encode confirmed expectations.

## Interfaces (planned `code_review/api.py`)
| Function | Notes |
|---|---|
| `review(snapshot_id, target, budget) -> list[FindingId]` | Worker job from orchestrator `FUNCTIONAL_REVIEW` |
| `generate_tests(expectation_ids) -> list[GeneratedTest]` | Also used by Fortify regression tests |
| `propose_repair(finding_id, approval_id) -> PatchCandidateId` | Requires approval; Verify follows |

Outputs: `Finding(kind=functional)`, `GeneratedTest`, `TestRun`, `PatchCandidate`
([docs/12](../docs/12_DATA_MODELS_AND_CONTRACTS.md)).

## Dependencies
`shared/`; `code_intelligence.api` (context packs, expectations);
`security_agents` sandbox driver + `tests.run` / worktree tools; Verify agent;
`backend` LLM gateway and persistence.

## Planned layout
```
code-review/
  code_review/
    api.py  reviewer/  testgen/  repair/  prompts/reviewer/v1.md
  tests/
```

## First tasks
REVIEW-001 … REVIEW-003.

## Commands
None yet.
