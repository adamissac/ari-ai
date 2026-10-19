# v5 pre-registration (written and committed before any v5 run)

Decided with Alan on 2026-10-19, after the v4 reject (results/live-retrain-v4/PROVENANCE.md).

**Hypothesis.** v4's candidate got worse with more offline updates: val return fell from
−5.61 at update 2000 to −15.28 at 16000. This is out-of-distribution Q overestimation on a
small fixed dataset. A conservative Q-learning penalty should stop that degradation. A
bigger network should not, so the network is unchanged at (128, 128).

**The only change from v4.** The candidate is trained with discrete CQL(H),
`DDQNConfig.cql_alpha = 1.0`. The value 1.0 is fixed here and will not be tuned. It is the
weight commonly used for discrete-action CQL. Everything else is v4: `c_disrupt=1.0`, the
grant-aware detector, selection on the mean over `val_v4`, `train_v3`, the v3 noop-margin
grid, and v3 budgets.

**Holdout.** `configs/live/holdout_v5/` consists of night_batch, token_spray and
mixed_insiders, with seeds 44500–44529, 49200–49229 and 49600–49629. Its names and seeds
are disjoint from every other split (`test_holdout_v5_is_new_and_disjoint_from_everything_else`).
`configs/live/promotion.yaml` is unchanged.

**The one run:**

```sh
cd rl-defense
PYTHONPATH=.:../shared:../standards:../examples/payments-lite/target \
  .venv/bin/python -m rl_defense.live.pipeline --base-steps 30000 --rounds 3 \
  --epsilons 0.5,0.3,0.2 --updates 16000 --eval-every 2000 --val-episodes 8 \
  --rules-episodes 2 --seed 0 --action-space live_v3 --train-dir train_v3 \
  --val-dir val_v4 --holdout-dir holdout_v5 --noop-margins 0,0.1,0.2,0.3,0.5 \
  --c-disrupt 1.0 --delegation-aware-detector --val-selection scenario_mean \
  --cql-alpha 1.0 --out runs/live/retrain-v5 --evidence-dir results/live-retrain-v5
```

**How the result will be read, fixed now:**
- The gate decides, as always. Promotion still needs a human approver.
- Whether CQL fixed the degradation is answered by the val curve, using val data only. It
  is fixed if the selected snapshot in at least two of three rounds is later than update
  2000, or if the round-2 val return at 16000 updates is within 1.0 of its best.
- If the candidate does not beat `always_block_principal` on holdout return, the report
  says so. As agreed, that ends the learned-policy track on this app.
