# v6 pre-registration (written and committed before any v6 run)

Decided with Alan on 2026-10-19, after the v5 reject (results/live-retrain-v5/PROVENANCE.md).
RL stays the defense. The rule is used only as a **teacher**.

**Hypothesis.** v4 and v5 failed because of the data. The candidates learned from about
6k offline transitions around the sim policy, in which blocks were only 3–5% of actions.
With expert demonstrations in replay and about 150k online live transitions, a Q-learner
can learn the blocking behaviour and, through TD, where to deviate from the teacher.

**Method** (`rl_defense/live/online.py`, DQfD after Hester et al. 2018):
1. **Expert, chosen on train only.** The best train return among the tuned v3 rules
   (`tune_rules_v3`, the same tuning that sets the gate's static-rules bar),
   `always_block_principal`, `always_block_principal_long` and
   `always_block_top_principal_long`. It is scored on 2 episodes per train scenario.
2. **Demonstrations.** 20 expert episodes per `train_v3` scenario (100 episodes, 3000
   transitions). They stay permanently in a separate demonstration buffer.
3. **Fresh network** in live_v3 dims (55 obs, 25 actions), (128, 128), with no simulator
   prior. Pretraining: 5000 updates on demonstrations only, with TD plus the large-margin
   loss, λ = 1.0 and margin 0.8.
4. **Online.** 150,000 live environment steps on `train_v3`, cycling through the scenarios.
   Training episode seeds are drawn only from the train band (0–9999). ε-greedy over valid
   actions, ε 0.3→0.05 over 75k steps. One update per step, batch 64, with 25% demo rows in
   every batch (margin loss on those rows only). lr 3e-4, Double DQN, γ 0.99, hard target
   update every 1000 updates, buffer 100k.
5. **Selection on `val_v4`.** Every 15k steps, plus once after pretraining, by the
   unweighted mean over the four val scenarios with 8 episodes each. Noop margins
   {0, 0.1, 0.2, 0.3, 0.5}. The best (snapshot, margin) is kept.
6. **The v4 loop**: `c_disrupt=1.0`, grant-aware detector, action space live_v3.
7. **Holdout once** on `configs/live/holdout_v6/` (customer_turned_attacker,
   rotating_outsider_busy_books, slow_pair; seeds 45500, 46500 and 47500, 30 episodes each).
   Its names and seeds are disjoint from every split
   (`test_holdout_v6_is_new_and_disjoint_from_everything_else`). Policies: deployed (sim),
   candidate, tuned rules, noop, always_isolate_payments, and the three block baselines,
   which include the expert. `configs/live/promotion.yaml` is unchanged. Never promote.

**The one run:**

```sh
cd rl-defense
PYTHONPATH=.:../shared:../standards:../examples/payments-lite/target \
  .venv/bin/python -m rl_defense.live.online --base-steps 30000 --rules-episodes 2 \
  --seed 0 --train-dir train_v3 --val-dir val_v4 --holdout-dir holdout_v6 \
  --out runs/live/retrain-v6 --evidence-dir results/live-retrain-v6
```

**Seen before the run.** Unit tests on tiny synthetic scenarios. The online pipeline smoke
test (train_v3 and val_v4 at 1 episode, a 150-step candidate, the exposed holdout_v2).
One timing check on a synthetic train-band scenario (0.3 s per episode), used to set the
step budget. No policy was run on holdout_v6.

**How the result will be read, fixed now:**
- The gate decides.
- The report gives the paired return of the candidate minus the expert on holdout. A
  learned policy that only ties its teacher is reported as a tie, not as RL beating rules.
- Whatever the outcome, no tuning follows on holdout_v6.
