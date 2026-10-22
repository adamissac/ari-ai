# Phase 1 evidence review handoff

PR #388 remains unmerged. Verification now rejects incomplete source manifests,
truncated registered seed selections, and inconsistent raw request outcomes.
Policy certification loads exactly the checkpoint bytes whose digest was checked.

Validation: 44 focused tests passed; the archived 140 episodes / 4,200 transitions
verified successfully. Original execution and reporting artifacts are unchanged.
The previous revision passed 354 RL tests in CI; the new revision requires CI.
No research training, Phase 2 implementation, promotion, or deployment occurred.

Third review: scenario definitions must match the pinned training benchmark; statistical
settings are fixed before bootstrap work starts; all post-creation setup exceptions
produce a failure audit record without retry. The 39-test focused run and the added
scenario-tampering regression both passed. Original measurements are preserved.

Fourth review: source fingerprints are checked against actual recorded Git blobs;
successful foreign reads must retain their compromise flag; Phase 1 root flags
are enforced. No original measurement is changed. All 44 focused tests passed; archived 140 episodes / 4,200 transitions verify.

Proposed next readiness work is recorded in NEXT_GATE.md. Its budgets and thresholds
remain unset, and it authorizes no experiment or training.

Fifth review adds deterministic in-memory training-fixture reconstruction, source-bound
YAML/rule inputs, bounded gzip parsing, exact runtime checks and fixed scope metadata.
51 focused tests passed. Owner subsequently authorized merge; wait for latest CI and
review, and retain the existing production build-skip rule for research-only paths.
No original measurement or v6 artifact is changed.

Sixth review: bounded artifact reads are captured once and reused for digest checks,
metadata, decompression, adaptation, reconstruction, summary and source-commit proof.
A swap-after-capture regression covers the race. Latest focused validation pending.

Seventh review anchors the review manifest in the trusted checkout commit, records
the full reproduction dependency closure separately from unknown historical closure,
and supersedes the immutable legacy script with an anchored supported reader.
