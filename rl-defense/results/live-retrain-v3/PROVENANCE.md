# Provenance of the v3 live-retraining evidence (long and targeted blocks, delegated reads)

How the numbers in [REPORT.md](REPORT.md) were produced, what was seen before the run, and
how to read the verdict.

## Reproduce

```sh
cd rl-defense
PYTHONPATH=.:../shared:../standards:../examples/payments-lite/target \
  .venv/bin/python -m rl_defense.live.pipeline --base-steps 30000 --rounds 3 \
  --epsilons 0.5,0.3,0.2 --updates 16000 --eval-every 2000 --val-episodes 8 \
  --rules-episodes 2 --seed 0 --action-space live_v3 --train-dir train_v3 \
  --val-dir val_v3 --holdout-dir holdout_v3 --noop-margins 0,0.1,0.2,0.3,0.5 \
  --out runs/live/retrain-v3 --evidence-dir results/live-retrain-v3
```

All v2 hyperparameters are the same (results/live-retrain-v2/PROVENANCE.md). The new flags
are `--action-space live_v3`, the three `--*-dir` flags, and `--noop-margins` (the fix in
"The raise_monitoring diagnosis" below). The margin grid was fixed before the run.
Checkpoints and raw datasets are in `runs/` (git-ignored); their SHA-256 digests are in the
manifests here. Wall clock: about 22 minutes on one CPU (2026-10-19 05:38 to 06:00 UTC);
rules tuning (384 grid points) took most of it. The run reports `git_sha` `e905ce8`.
The deployed checkpoint digest (`0c5b7d06…`) differs from v2's (`967e4fcb…`) for the reason
given there: the digest covers the embedded manifest (git SHA, timestamp).

## What changed from v2

- **Legitimate cross-tenant access.** Bookkeeper fixtures (`dave`, `erin`) are authorized
  to read a client's payments (`delegations`, `adversary.DelegateProfile`). Their reads
  are benign. The gateway's detector only compares the token's principal with the object's
  owner, so it flags them like an attack. Blocking "whoever is flagged" now costs real
  availability (`test_blanket_blocking_has_a_real_availability_cost_without_any_attack`).
  Detection still never reads the generator's `is_attack` label.
- **Identity-switch leak.** Two new live-only actions, both strict extensions (v2 indices
  unchanged): 23 `block_principal_long` (block or extend every flagged principal for 10
  windows) and 24 `block_top_principal_long` (the same, only for the heaviest flagged
  principal). There are six new detector features (obs 49..54). Tests:
  `test_long_block_closes_the_identity_switch_leak`,
  `test_long_block_extends_a_short_block_and_short_never_shortens_long`,
  `test_top_target_spares_the_delegate_seen_in_the_same_window`.
  The new names are not in `shared.rl.DefenseActionName`. They are proposed to Srihith in
  `coordination/messages/20261019T053641Z-alan-to-srihith-adam-long-block-actions.md`.
- **Rules get every new action.** `evaluate.tune_rules_v3` runs two stages on train only.
  Stage 1 is the v2 grid in the v3 loop. Stage 2 fixes the stage-1 docs/09 thresholds and
  searches the grid block threshold × minimum per-principal volume × long mode (never,
  always, repeat, extend, outsider) × long target (all, top), 144 points.
- `configs/live/promotion.yaml` is **unchanged**. DefenseSimEnv is untouched.

## The raise_monitoring diagnosis (v2 candidate, train/val data only)

The v2 candidate spent 110 of 240 val steps on `raise_monitoring`. Live, that action only
rescales the reported anomaly score
(`test_raise_monitoring_has_no_containment_effect_live`). Measured on the v2 run's train
datasets and val episodes:

- At the selected snapshot (update 2000), the Q-values were still at the simulator's scale:
  mean Q(s,a) ≈ +1.5 against measured discounted returns ≈ −3.7 (Q − G ≈ +4.5 to +7.3 for
  every action). With hard target updates every 1000 steps and 30-step episodes, 2000
  updates propagate only about two backups. The value function was mostly still the sim
  prior.
- On val states, Q(raise_monitoring) − Q(noop) averaged +0.24, against a true gap of −0.02
  (the action cost). Roughly ten effect-free actions (raise_monitoring on 5 nodes,
  reassessment, escalation) tie with noop up to that noise. Argmax over about ten near-ties
  rarely lands on noop.
- Tried first: Monte Carlo return calibration before the TD updates. On val it did not
  remove the behavior: 90 of 240 steps were still on monitoring, and val return was −5.45
  vs −4.93. Not adopted.
- Adopted: a greedy abstention margin, `DDQNConfig.noop_margin`. A non-noop action is taken
  only if its Q beats Q(noop) by the margin. The margin is chosen per snapshot on **val**.
  On the v2 candidate, val return rose monotonically with the margin (−4.93 at 0 to −4.60 at
  0.5), and containment did not change.

## Order of events

1. Code, `configs/live/train_v3`, `val_v3` and `holdout_v3` were committed in `37cfdba`
   before any policy ran on holdout_v3. `holdout_v3` (three_identities_delegated,
   heavy_reconciliation, rogue_bookkeeper; seeds 48000–49029) is disjoint from every other
   split's names and seeds (`test_holdout_v3_is_new_and_disjoint_from_everything_else`).
   The follow-up commit `e905ce8` (tests, a fix to the top-target block, the long-block
   mask, the v3 checkpoint registration) did not touch any config file
   (`git diff --stat 37cfdba e905ce8 -- rl-defense/configs` is empty).
2. Before the run, the author ran policies on **train_v3 only**, to check the design:
   hand-written block policies at 4 episodes per scenario. The result was that a simple
   "long-block the heaviest flagged principal above a volume threshold" rule already scored
   −4.45 on train. Because of this, the `outsider` rule mode was added, to make the rules
   bar stronger rather than weaker. The v2 diagnosis used only v2 train datasets and val.
3. **No policy was evaluated on holdout_v3 before the final run.** The v3 pipeline smoke
   test uses the already exposed `holdout_v2`.
4. The final run evaluated every holdout_v3 episode once. Nothing was re-run or tuned.
5. After the run, one val-only diagnostic of the selected candidate (below).

## Verdict and interpretation

`reject`. Four of seven checks fail: availability 0.797 < 0.85, no-attack duty
0.622 > 0.5, beats_static_rules −13.87 vs −10.98, and a per-scenario regression of −3.62
on heavy_reconciliation. The candidate does beat the deployed policy: +2.01 [0.94, 3.06].

What the evidence says:

- **v3 does give a learned policy something to beat, but this candidate did not beat it.**
  Fixed rules are no longer optimal. On holdout, `always_block_principal_long` (−10.61)
  beats the tuned rules (−10.98). On val, the candidate beat the tuned rules by about 3
  (−7.21 vs −10.31) by trading compromise for availability (0.42 / 0.96 against
  0.12 / 0.53). That trade did not transfer to holdout_v3.
- **Selection overfit the single val scenario.** All three rounds selected the largest
  margin, 0.5, which lies at the edge of the grid. Without the margin the same network
  scores −13.08 on val and spreads its actions over rate_limit, monitoring, isolate,
  reassessment and escalation (noop in 4 of 240 steps). The Q-function itself is still poor;
  the margin hides this on val by abstaining. On holdout the abstaining policy leaks (0.66
  compromise), and on heavy_reconciliation it is worse than noop. In that scenario the
  bookkeepers' reconciliation bursts out-read a 3-request insider, so a "heaviest
  principal" block hits the delegate.
- **The availability floor is out of reach for every containing policy on holdout_v3.**
  Every policy with compromise ≤ 0.26 has availability ≤ 0.52, because some delegate is
  flagged in nearly every window. Blocking delegates, or isolating the payments node, costs
  their traffic. Only abstention clears 0.85. This is a property of the scenarios and the
  gate together, and v4 needs it addressed (for example, a per-principal target choice, or
  scenarios where delegates are not flagged every window). A human must decide whether the
  0.85 floor is right for scenarios with standing legitimate cross-tenant reads.
  `promotion.yaml` was not touched.
- The identity-switch leak itself is closed by the new control: on
  three_identities_delegated, `always_block_principal_long` compromises 0.30 against 0.45
  for `always_block_principal`. The long block's price is availability.

Lab evidence only (RQ-005). Promotion would still need a human `usr_*` approver via
`rl_defense.live.registry`; the gate's decision here is reject, and nothing was promoted.
