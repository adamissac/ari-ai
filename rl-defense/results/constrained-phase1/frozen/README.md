# Phase 1 baseline evidence

Completed140episodes /4,200scored windows: five fixed policies × seven train_v8
scenarios × four registered seeds. Reset warmup traffic is separate. This is an
engineering baseline check, not training, a v11 study or a promotion decision.
No holdout/validation evaluation or tuning. Source was published before execution:
`9d6460487275d25cc31194d7b603196d436c4485`, tree
`22c2f7f50c36e5fe5b7eb1d26c41b1b314438e4a`; local equivalent commit `43b7110`.
Shell network was unavailable; GitHub connector published the exact matching tree.
The CLI checked that tree equality; both commit identities are retained in config.

All baselines use live_v3 with the same research capability mask, delegation-aware
detector and platform severity draws. V6 weights are unchanged; **v6_shielded is not
the original v6 policy selection rule**. Saved v10 rules were reused without tuning.
Cost-aware uses at most two new short blocks with payments finding context; it has
no learned cost model and provides no cumulative-damage guarantee.

## Measured outcomes

Compromise and availability pool request numerators/denominators. Costs/interventions
are mean per episode. Cost gamma=1. Parentheses are95% bootstrap intervals from2,000
resamples(seed17) of whole independent seed clusters, stratified by scenario membership.
Four seeds/scenario are too few for a strong safety claim; no training-seed uncertainty
or improvement hypothesis is tested. Complete per-scenario/pooled intervals and all
counts/records are retained in summary.json and raw artifacts.

| Policy | Attack compromise | Benign availability | Quiet false disruption | Mean interventions | Mean cumulative benign cost |
|---|---|---|---|---|---|
| cost_aware | 93.16% (86.27–98.57) | 99.50% (99.18–99.77) | 0.32% (0.09–0.57) | 0.536 | 1.250 |
| fixed_short_block | 20.35% (17.36–23.35) | 94.36% (93.62–95.19) | 2.11% (1.62–2.61) | 4.857 | 14.214 |
| noop | 100.00% (100.00–100.00) | 100.00% (100.00–100.00) | 0.00% (0.00–0.00) | 0.000 | 0.000 |
| tuned_rules_shielded | 9.33% (7.75–11.25) | 92.68% (91.64–93.74) | 3.95% (3.19–4.83) | 3.536 | 18.464 |
| v6_shielded | 9.99% (8.55–11.87) | 90.42% (89.00–91.92) | 6.73% (5.15–8.18) | 15.071 | 24.143 |

The constrained rule's99.50% availability accompanies93.16% compromise; preserving
traffic by almost never intervening does not solve defense. Frozen shielded v6 and
rules trade more denials for fewer compromised reads. No cross-generation ranking
against historical v6 return−5.30 or95.2% availability is valid: action masks, contexts,
scenarios and objective units differ. Noop's zero cost does not imply safety.

## Historical compatibility analysis (read only)

`read_legacy.py` / `legacy_readiness.json` adapted five existing duration-screen **train**
artifacts after their original index/RUN/scenario pins verify:280episodes /8,400
transitions, all with observed aggregate cost;280first masks unknown,8,400behavior
propensities unknown,8,400delegated-denial attributions unknown. This is a new explicitly
versioned descriptive objective view, not a rewritten historical result or counterfactual
policy evaluation. Those old trajectories overlap this baseline's train seeds; do not
pool them as independent samples. No historical artifact was modified.

## Reproduce and verify

Use Python3.12.14 and versions in config.json (NumPy2.5.4, Pydantic2.14.1, Torch2.14.1,
Gymnasium1.4.0, FastAPI0.150.0, httpx0.28.1, PyYAML6.0.3). From repo root:

```sh
export PYTHONPATH="$PWD/rl-defense:$PWD/shared:$PWD/standards:$PWD/examples/payments-lite/target"
python -m rl_defense.research.evaluate verify --output rl-defense/results/constrained-phase1
python rl-defense/results/constrained-phase1/read_legacy.py
```

Verifier checks artifact hashes, exact source hashes, raw requests→outcomes→versioned
r/c records, full seed/scenario sets, complete chains, bootstrap and every saved summary.
If current product source changes, it **refuses** with the recorded-source instruction;
use execution source `9d64604` plus these preserved artifacts in an isolated checkout.
It never silently reinterprets these results under future source. `REPORT_EVIDENCE.json`
additionally pins post-run documentation/readiness/registry proof; EVIDENCE.json retains
the original execution-artifact pins unchanged. A pin requires a trusted Git/index root,
not a claim that a self-authored hash is an independent signature.

The execution command, before any results:

```sh
python -m rl_defense.research.evaluate run --output rl-defense/results/constrained-phase1 --episodes 4 --published-commit 9d6460487275d25cc31194d7b603196d436c4485 --published-tree 22c2f7f50c36e5fe5b7eb1d26c41b1b314438e4a
```

Do not rerun into this directory; existing outputs are rejected. A separately authorized
replication would use a new empty output path and the exact recorded source/config.
No original checkpoint/registry or customer recommendation path is modified. The runtime
registry digest before/after remains c345593354856c50559ba16611853a0e4936a7efc11fa5704c224d3189271408.

Decision: **no-go now** for constrained-DDQN/CQL; conditional preference for a small
cost-aware DDQN ablation only after control feasibility, data/state support and a
preregistered cost budget. Phase2 is not started. See the complete audit and decision
under docs/research/constrained-rl-phase1.
