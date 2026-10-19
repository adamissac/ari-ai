# Provenance of the v2 live-retraining evidence (`block_principal`)

How the numbers in [REPORT.md](REPORT.md) were produced, and what was seen before the run.

## Reproduce

```sh
cd rl-defense
PYTHONPATH=.:../shared:../standards:../examples/payments-lite/target \
  .venv/bin/python -m rl_defense.live.pipeline --base-steps 30000 --rounds 3 \
  --epsilons 0.5,0.3,0.2 --updates 16000 --eval-every 2000 --val-episodes 8 \
  --rules-episodes 2 --seed 0 --action-space live_v2 --holdout-dir holdout_v2 \
  --out runs/live/retrain-v2 --evidence-dir results/live-retrain-v2
```

The hyperparameters are the same as v1's (results/live-retrain/PROVENANCE.md); only
`--action-space` and `--holdout-dir` are new. Checkpoints and raw datasets live in `runs/`
(git-ignored); their SHA-256 digests are in the manifests here. Wall clock: about 10 minutes
on one CPU (2026-10-19 04:45 to 04:55 UTC). The deployed checkpoint digest (`967e4fcb…`)
differs from v1's (`abc06bef…`) even though the seed and step count match. The digest
covers the embedded manifest (git SHA, timestamp), not only the weights.

## Order of events

1. `configs/live/holdout_v2/` (two_identities, token_rotation, outsider_and_insider; seeds
   45000–47029, disjoint from v1 holdout seeds) was written and committed in `f222b09`,
   together with the control and its tests. The run reports that same `git_sha`.
2. `configs/live/promotion.yaml` is **unchanged** from v1. No criterion was changed.
3. **No policy was evaluated on holdout_v2 before the final run.** The tests use it only
   for hygiene checks (names, seed disjointness, identity fields). They do not run
   episodes on it. The v2 pipeline smoke test runs on the already-exposed v1 holdout.
4. Before the run the author ran policies on train and val only:
   - unit tests on hand-built scenarios;
   - one timing check of a block rule on the train split;
   - after the run, one action-count check of the candidate on val, for the
     interpretation below.
5. The final run evaluated every holdout_v2 episode once. Nothing was re-run or tuned.

## Fairness choices made before the run

- The threshold-rules baseline also gets `block_principal`: the rules grid gains a
  `block_anomaly` threshold (1.1 = never), tuned on the train split like the other
  thresholds. A v2 candidate therefore has to beat rules that can use the new control too.
  `threshold_rules_no_block` (best grid point without blocking) is reported for context only.
- The deployed sim policy runs on the first 48 features and 22 mask entries, so it cannot
  block. That matches what is deployed today.

## Verdict and interpretation

`reject`. The candidate passes six of seven checks, including the availability floor
(0.889 vs 0.85; v1 reached 0.759). It fails `beats_static_rules`: −7.29 vs −6.96. On every
holdout scenario the tuned rules match `always_block_principal` exactly, and the candidate
matches them on compromise, availability and false disruption. The return gap comes from
extra non-noop actions: 0.67 vs 0.23 actions per step. On val the candidate spends most of
those on `raise_monitoring`, which costs reward and does not contain anything.

Findings the designers should know:
- `block_principal` makes the availability floor reachable: candidate availability is 0.889,
  against 0.711 for the best rules without blocking.
- When the attacker is also a legitimate customer (Bob), blocking that customer costs
  their own payments reads. The gateway cannot separate the two.
- `two_identities` exposes a weakness of the fixed 3-window block: with two identities
  taking turns each window, each identity is unblocked every other attack window. Every
  blocking policy leaks 64% there, against 22% for node isolation rules.

Lab evidence only (RQ-005). Promotion still needs a human `usr_*` approver via
`rl_defense.live.registry`, and the gate's decision here is reject.
