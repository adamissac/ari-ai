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

Eighth review pins replay topology and the v6 sidecar to the source commit. The
sidecar must also equal the manifest embedded in the hash-pinned checkpoint, with
only the canonical filename added. No original artifact is changed.

Ninth review captures scenario, topology, rule and sidecar bytes before parsing or
reconstruction, passes captured topology into the verification-only loop, and enforces
the original execution-index digest from the Git-anchored review manifest.

The supported legacy reader also bounds index/run/trajectory reads and adapts private
captured trajectory snapshots, preserving original artifact names and digests.

Tenth review validates the local execution revision for new bundles, checks the
anchored original reporting index/files, and certifies from private commit-owned
read-only source so lazy Python imports cannot race caller-checkout edits.

Review-manifest validation now covers every listed code, documentation and artifact
path, including bundle copies, with bounded captured source reads. Regression cases
cover independent drift of proof.py, the supported legacy reader and verification docs.

Standalone legacy certification now uses the same private source snapshot and
anchored source/runtime checks. The active results README invokes the supported
reader; its original bytes are preserved under frozen/README.md and the unchanged
reporting index resolves that known alias under review schema v2.

CI found a portability error in the snapshot-I/O component test: it invoked archived
macOS runtime certification on Linux. The test now targets only the captured-I/O
component; a dedicated wrong-runtime rejection test retains the strict public gate.
The production source/runtime checks are unchanged. Prior CI: 394 passed, 1 fixture
failure; latest revision requires CI before merge.

Final snapshot review: both public entry points capture the verifier commit before
checking artifacts. The private clone skips checkout until that exact commit is
selected in detached mode, and verifies its identity before imports. The regression
moves the source branch during cloning and confirms only the captured code executes.

Integration with main preserves its Live Defense changes. Archived certification
uses published revision `31ab052941ebf1b3678a2610e5c4374d83606aa0`, because the
later shared-contract source differs from the original study closure. Historical
source checks remain strict; no evidence pins or measurements are relaxed.
