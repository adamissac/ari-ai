# Phase 1 verification results

The focused research suite passes **51 tests**, covering request and transition
validation, seed selection, source provenance, named policy decisions, checkpoint
integrity, capability limits, deterministic accounting, and registry preservation.
The previous published revision passed **354 RL tests** in CI. CI must rerun for
this revision. Formatting, lint, and Markdown link checks passed locally.

Read-only verification accepted all **140 episodes and 4,200 transitions** in the
archived baseline study. Verification reconstructs the deterministic owned in-process training fixture from
saved seeds/actions and compares decision inputs and every recorded request outcome.
It saves no replacement study data, trains no policy, and never replays holdout.
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

Third review: scenario definitions must match the pinned training benchmark; statistical
settings are fixed before bootstrap work starts; all post-creation setup exceptions
produce a failure audit record without retry. The 39-test focused run and the added
scenario-tampering regression both passed. Original measurements are preserved.

Fourth review validation: all 44 focused research tests passed. Read-only verification
again accepted the original 140 episodes and 4,200 transitions. Source fingerprints
now match recorded Git blobs, compromise labels are checked in both directions,
and the root index must retain its Phase 1 flags.

Fifth review: exact recorded Python/dependency versions are required. Non-Python
scenario/rule inputs must match their source commit (or the immutable historical
fingerprint). Compressed input is limited to 8 MiB, expanded input to 64 MiB, before
JSON parsing. Scope metadata is fixed. Expected units are checked before replay.
All 51 focused tests passed before the final ordering-only change.

Seventh review: the review manifest is compared with its Git HEAD blob before its
hashes are trusted. New bundles record the complete installed distribution closure.
The original study did not capture that closure; it remains explicitly unknown.
REVIEW_RUNTIME.json records the current reproduction environment separately and is
Git-anchored. Successful verification reports its own source commit and this limit.

Use `python -m rl_defense.research.legacy` for anchored legacy readiness checks.
The original result-directory read_legacy.py is frozen archival source, retained for
REPORT_EVIDENCE.json integrity; it is superseded and must not be used to certify
mutable bundles. The supported reader anchors the historical root index digest.
