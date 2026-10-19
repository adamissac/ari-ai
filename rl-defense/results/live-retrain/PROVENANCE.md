# Provenance of the v1 live-retraining evidence

How the numbers in [REPORT.md](REPORT.md) were produced, including what the author saw
before the final run.

## Reproduce

```sh
cd rl-defense
PYTHONPATH=.:../shared:../standards:../examples/payments-lite/target \
  .venv/bin/python -m rl_defense.live.pipeline --base-steps 30000 --rounds 3 \
  --epsilons 0.5,0.3,0.2 --updates 16000 --eval-every 2000 --val-episodes 8 \
  --rules-episodes 2 --seed 0 --out runs/live/retrain-v1 --evidence-dir results/live-retrain
```

Checkpoints and raw datasets are written to `runs/` (git-ignored, about 20 MB); their
SHA-256 digests are in the manifests here. The per-round validation returns
(−11.73, −8.90, −7.27) were identical in an earlier independent prototype run, so the
pipeline is deterministic on this machine. Wall clock: about 8 minutes on one CPU.

## Order of events

1. Code for the gate (`PromotionCriteria` defaults in `rl_defense/live/evaluate.py`) was
   written before any holdout evaluation. `configs/live/promotion.yaml` holds the same
   values. Code and criteria were committed in `33d2e17` before the final run.
2. **Holdout exposure during development (3 evaluations before the final run):**
   - a 5-episode/scenario check of `noop`, `always_isolate_payments` and the deployed
     policy, to size the experiment;
   - a 10-episode/scenario evaluation of a one-round prototype candidate. Afterwards
     two changes were made: (a) the `no_attack_defense_duty` metric was redefined from
     "any isolate/rate-limit active on any node" to "legitimate traffic actually blocked",
     because controls on nodes that carry no traffic have no measurable effect (the
     validation history showed the same artefact); (b) retraining moved from one round to
     three aggregated rounds, because validation return peaked early and then degraded;
   - a 10-episode/scenario evaluation of the three-round prototype.
3. The final run evaluated every holdout episode once. The candidate was chosen by
   validation return only. No criterion threshold, reward weight or holdout scenario was
   changed after any holdout evaluation.

## Consequence

The holdout is not pristine: the metric definition and the multi-round design were
chosen with holdout numbers in view. The verdict is `reject`, so the exposure did not
favour promotion. The reported candidate-vs-deployed gain may be slightly optimistic. A v2
must be judged on new holdout scenarios that nobody has evaluated.
