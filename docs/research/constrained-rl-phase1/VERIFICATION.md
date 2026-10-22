# Phase 1 verification results

The focused research suite passes **35 tests**, covering request and transition
validation, seed selection, source provenance, named policy decisions, checkpoint
integrity, capability limits, deterministic accounting, and registry preservation.
The previous published revision passed **354 RL tests** in CI. CI must rerun for
this revision. Formatting, lint, and Markdown link checks passed locally.

Read-only verification accepted all **140 episodes and 4,200 transitions** in the
archived baseline study. This verification uses saved observations and fixed policy
inference; it does not collect new HTTP episodes, train a policy, or replay holdout.
Historical adapter verification covered 280 episodes and 8,400 transitions, retaining
unknown initial masks, propensities, and delegated costs. No OPE claim is made.

## Evidence integrity

The original execution and reporting artifacts remain byte-identical. The original
evaluator and source commit proof are preserved separately. Historical verification
requires the complete original source mapping and identical collection/adaptation
function ASTs. Later verifier changes are recorded in a separate review index.
Unknown schemas, incomplete source mappings, inconsistent request outcomes, false
policy labels, and declared sample sizes larger than registered capacity are rejected.
Checkpoint certification loads exactly the bytes whose digest was checked.

The source-manifest scanner exception remains restricted to exact paths, lines,
and source digests. A synthetic credential added to the same manifest is detected.
No secret-scanning file exclusion was introduced.

## Handoff boundary

PR #388 remains unmerged. No promotion, deployment, new control, research training,
or Phase 2 implementation occurred. The v6 checkpoint and registry are unchanged.
See DECISION.md for the no-go decision and conditions for future work.
