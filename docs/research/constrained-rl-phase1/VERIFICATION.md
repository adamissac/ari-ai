# Phase 1 verification results

The final focused research suite passed **69 tests** on the recorded reproduction
runtime. The suite covers request/transition invariants, independent seed units,
capability limits, source and checkpoint provenance, wrong-runtime rejection,
immutable source snapshots, bounded captured artifact I/O, reporting preservation,
and complete review-manifest drift checks. No existing test was removed or weakened.

The exact archived study verifies: **140 episodes / 4,200 transitions**, with every
fixed-policy action, observation, mask, request label, identity, outcome and saved
summary reproduced. The supported legacy reader reproduces the original readiness
report exactly: **280 episodes / 8,400 transitions**. Neither check selects a policy,
records replacement study data, trains a model, or executes holdout.

## Supported commands

Run from a reviewed repository revision with the recorded Python runtime, dependency
profile, and package paths configured for RL, shared contracts, standards and the
owned payments fixture:

```sh
python -m pytest -q rl-defense/tests/test_constrained_research.py
python -m rl_defense.research.evaluate verify --output rl-defense/results/constrained-phase1
python -m rl_defense.research.legacy
```

Both public certification commands execute their replay/adaptation code from a
private read-only checkout of committed source. They validate captured artifact
bytes, source/semantic-input fingerprints and the recorded runtime before issuing
a result. Linux CI tests these components with controlled fixtures; its interpreter
is deliberately rejected for archived macOS certification. The production runtime
gate was retained when correcting the portable snapshot-I/O unit test.

## Evidence integrity and limits

Original measurements, execution configuration, trajectories, summaries, both
original evidence indices and the v6 checkpoint/registry are unchanged. The original
README is preserved byte-identically in `frozen/README.md`. Review schema v2 maps the
unchanged reporting index's README pin to that frozen copy, and separately pins the
active README with its corrected supported command. The old result-directory
`read_legacy.py` remains immutable archival source and is not a supported verifier.

The review manifest is anchored in Git before every listed code, document and
artifact hash is checked. Historical execution/reporting roots are enforced;
collection/adaptation ASTs and the original source fingerprints must match. New
bundles resolve both publication and local execution revisions to the source tree.
Captured scenario, topology, rule and checkpoint-sidecar inputs are source-bound.
The sidecar must also match the manifest embedded in the pinned checkpoint bytes.

New bundles record the complete installed dependency closure. The original study
did not record its transitive closure; it remains explicitly unknown. A separately
Git-anchored `REVIEW_RUNTIME.json` records the reproduction runtime. Successful
baseline verification reports both the original study source and the verification
source commit, rather than attributing later verifier code to the old execution.

Compressed artifacts are limited to 8 MiB and expanded artifacts to 64 MiB before
JSON interpretation. Statistical settings, scenario/sample identity, scope metadata
and Phase 1 flags are fixed before computation. Unknown schemas, unsupported inputs,
false provenance, missing units and changed data fail verification. Setup failures
produce an audit record without automatic retry.

The source-fingerprint secret-scan exception is restricted to exact paths, lines
and digests. A synthetic credential in the same manifest is still detected; no
file/history exclusion was added. Lint/format and 524 Markdown link checks pass.
Current-head complete CI remains the merge gate; its final receipt is in PR #388.

## Decision and owner boundary

The owner explicitly authorized merge after Phase 1. The existing Vercel ignore
commands return skip-build for these research-only paths against current main.
No deployment command, promotion, new control, customer-facing action, new research
training or Phase 2 implementation occurred. V6 remains unchanged. The architecture
decision stays **no-go for constrained DDQN or CQL now**; NEXT_GATE.md records the
proposed feasibility work and the owner decisions required before any new study.
