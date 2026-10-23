# Adaptive defense readiness, research assessment 0.1

Verdict: **NO-GO for new RL training**. Algorithm recommendation: **Option C**.
This is a research assessment and pure observation adapter, not pilot readiness,
a new environment benchmark, an experiment launch, or checkpoint promotion.

Audited base main: `3d540d90` (full identity in Git history). Owner request follows
merged PR #414. Branch: `research/rl-adaptive-defense-readiness`, RL-CMDP-007.

- [Current state and evidence audit](AUDIT.md)
- [CMDP formulation and limits](CMDP.md)
- [Observation specification](OBSERVATIONS.md)
- [Action feasibility](ACTIONS.md)
- [Reward and separate costs](OBJECTIVE.md)
- [Dataset readiness](DATASET.md), [machine-readable inventory](DATASET_AUDIT.json)
- [Deterministic baseline design](BASELINES.md)
- [Blocked future preregistration](PREREGISTRATION.md)
- [Formal decision and required owner choices](DECISION.md)

Implemented: an internal versioned pure observation adapter using trusted provider
snapshots, explicit unknown channels, prefix-only cutoff construction, five-slot
candidate action mask with only noop enabled, independent action rejection, and a
fixed hash-anchored read-only inventory of training archives. No collection,
training, counterfactual evaluation, production adapter or new Gymnasium environment.
Current simulator/live layouts, all historical artifact bytes and v6 are untouched.

The strongest appropriate read-security baseline is trusted deterministic request
authorization plus no adaptive intervention. The finite authored evidence supports
that guard on those cases only; it does not establish population safety or timing.
The existing driver is exogenous and has no demonstrated residual availability,
resource-consumption, or investigation-resolution task under that guard. We stop
before inventing intervention benefit or claiming a sequential learning problem.

Run the inventory without executing policies:
`PYTHONPATH=rl-defense:shared:standards python -m rl_defense.research.adaptive_readiness`.
Its output must equal DATASET_AUDIT.json. These are derived diagnostics, never
replacement historical evaluation artifacts. Unit fixtures exercise adapter semantics;
they are not approved experimental collection or evidence of RL improvement.
