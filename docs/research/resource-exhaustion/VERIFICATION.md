# Resource research verification

Status: implemented unit mechanisms and Stage 2 preparation; **TRAINING NO-GO**.
No formal comparative feasibility study, research training, holdout evaluation,
checkpoint creation, promotion, or customer enforcement was performed.

## Fixed unit receipt

[Committed evidence index](unit-evidence/EVIDENCE.json) externally anchored SHA-256:
`b5f69ebc503647bebb2d42ef8cf7865eed1f5f42c16b60ececd84f09e5dcd86c`.
Captured once from source commit `1b5516c808602c91152c18b7460fe9aaa9cd8404`:
fixed mixed family, seed 0, four decision windows, threshold rule. The manifest
pins all seven source files, preregistration, configuration and dependencies.
Raw requests, per-unit consumed work, observable events, control ledger and
transitions are retained. The verifier checks the externally anchored file table,
transition schemas and temporal ordering, and reconciles reward/cost channels
against raw events. This is a unit receipt, not a policy comparison or estimate
of population performance. It remains ineligible for training. Pending requests
at the finite horizon are right-censored; future formal evaluation requires the
specified bounded terminal settlement, and a future training collector must
attribute its terminal costs before training is authorized.

To verify without collecting new data, call `verify_unit_bundle` with the index
hash above. The committed receipt test checks the original Git source bytes
when that history is available; hash validation also works in shallow checkouts.
Do not overwrite or regenerate this receipt after source changes.

## Executed local checks

- Resource environment and preparation suites: **46 passed** (1.25 seconds).
- Broader resource/adaptive-readiness/authorization/payment/constrained research
  regression selection: **213 passed** (21.40 seconds).
- Shared contract suite: **91 passed** (0.92 seconds).
- Scoped strict mypy: **7 source files**, no issues.
- Resource Ruff checks and formatting: passed. Markdown links: **580 files**,
  zero problems. Git whitespace check: passed.
- Final full-suite CI and independent PR review remain merge requirements; local
  selections are not substitutes for those checks.

Unit coverage includes finite capacity and work conservation, deadlines and
partial work, delayed controls and cleanup, collateral damage, valid masks,
cutoff and hidden-label isolation, deterministic seeds, vector-only baselines,
separate reward/cost storage, counterfeit evidence rejection, failure retention,
and bounded terminal settlement without rewriting policy transitions.

The Gymnasium checker uses a mask-aware sampler because arbitrary invalid
control actions intentionally raise. Independent tests cover invalid actions.
Work units and latency ticks are simulator accounting, not measured host CPU
or real HTTP latency. No claim of RL superiority or baseline ranking is supported.

## Required decisions

[Preregistration](PREREGISTRATION.md) proposes, but does not authorize, 600 episodes,
18,000 decisions, a bounded terminal drain, one CPU process, 512 MiB RSS and
600 wall seconds, with explicit per-family availability and intervention limits.
Approve or revise all numerical limits, sample sizes and statistical protocol
before formal comparison. Prior zero-denial payment-read requirements remain
unchanged. [Training preparation](TRAINING_PREPARATION.md) separately lists
future training approval and implementation gates; approving feasibility does
not authorize training. The next experiment is that fixed deterministic
comparison after approval, not RL training.
