# Agent 7 — Verify (Independent)

Status: **specified**. Contract base: [AGENT_CONTRACT](AGENT_CONTRACT.md).
Rules tested in [16](../16_TESTING_AND_VERIFICATION.md).

## Purpose
Decide, on executed evidence only, whether a patch fixes the finding without
breaking intended behavior. Verify is the only path to `verified`.

## Independence requirements
- Fresh sandbox(es) never used by Patch; fresh checkout at the snapshot SHA.
- Receives only: PatchCandidate diff artifact, the finding's original
  ValidationResult/failing test, the RemediationPlan, confirmed expectations.
- Receives **no** Patch transcript, notes, or self-assessment.
- Its verdict is computed by deterministic rules from check results; the LLM is
  used only to summarize results for humans.

## Checks (all must pass)
| Check | How |
|---|---|
| `original_check_now_fails_to_reproduce` | Re-run the same check template@version + params (security) or failing behavioral test (functional) against the patched target |
| `functional_suite_passes` | Run the project test suite; failures must be ⊆ baseline failures on unpatched snapshot |
| `generated_tests_pass` | Run tests added by Patch/review |
| `no_test_tampering` | Diff does not modify/delete tests encoding confirmed expectations |
| `diff_scope_ok` | Changed files ⊆ plan files ∪ new test files |

## Input — `VerifyInput`
`patch_id`, `finding_id`, `validation_result_id` or `failing_test_id`,
`remediation_plan_id`, `scope_id` (for re-check), baseline test results ref.

## Output — `VerificationResult`
`verdict`, `checks[]` with evidence, `sandbox_run_ids`, `reasons[]` (machine
reasons used for Patch retry), `summary` (LLM, non-authoritative).

## Tools & permissions
`code.read_span`, `expectations.for_subject`, `static.analyze`,
`checks.list_templates`, `checks.run_template`, `tests.run`, `patch.apply_fresh`.
Sandbox `test-runner` + `check-runner`; network none / target-only (scope-checked).
Write: none (read-only on the patch).

## Authorization & controls
- Security re-check passes `scope_guard` like Probe.
- Cannot modify the diff; cannot call Patch; cannot mark anything except via
  its output, which the orchestrator applies.

## Budget
10%; 8 min.

## Handoff
accepted → Fortify; rejected → Patch (attempt < 2) with `reasons`; else finding
`unresolved`.

## Success criteria / metrics
- 0 accepted patches that fail a later independent human re-check on fixtures.
- Detects planted bad patches (test-weakening, out-of-scope edits) in the
  fixture set: 100%.
