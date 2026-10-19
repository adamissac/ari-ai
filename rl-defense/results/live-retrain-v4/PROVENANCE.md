# Provenance of the v4 live-retraining evidence (final iteration)

How the numbers in [REPORT.md](REPORT.md) were produced, what was seen before the run, and
how to read the verdict. v4 is the last planned iteration of this experiment. No v5 is planned.

## Reproduce

```sh
cd rl-defense
PYTHONPATH=.:../shared:../standards:../examples/payments-lite/target \
  .venv/bin/python -m rl_defense.live.pipeline --base-steps 30000 --rounds 3 \
  --epsilons 0.5,0.3,0.2 --updates 16000 --eval-every 2000 --val-episodes 8 \
  --rules-episodes 2 --seed 0 --action-space live_v3 --train-dir train_v3 \
  --val-dir val_v4 --holdout-dir holdout_v4 --noop-margins 0,0.1,0.2,0.3,0.5 \
  --c-disrupt 1.0 --delegation-aware-detector --val-selection scenario_mean \
  --out runs/live/retrain-v4 --evidence-dir results/live-retrain-v4
```

Every hyperparameter is v3's (results/live-retrain-v3/PROVENANCE.md), including the
margin grid and the rules grids. The only new flags are the three v4 fixes and the
`val_v4` / `holdout_v4` directories. Checkpoints and raw datasets are in `runs/`
(git-ignored), and their SHA-256 digests are in the manifests here. Wall clock: 2026-10-19
06:39 to 07:26 UTC on one CPU. The run reports `git_sha` `0220e7d`. The deployed digest
(`6c130629…`) again differs from earlier runs only because the digest covers the embedded
manifest.

## The three v3 causes and the v4 fixes (decided by Alan before the run, not tuned afterwards)

1. **Reward not aligned with the gate.** `c_disrupt` was 0.5, which made giving up about
   half of legitimate traffic return-optimal while the gate demands 85% availability. v4
   uses `c_disrupt=1.0`: a blocked legitimate request costs as much as a compromised read,
   each normalized per window. This is `evaluate.V4_LOOP_OVERRIDES` / `--c-disrupt 1.0`. The
   `LoopConfig` default stays 0.5, so v1-v3 reproduce
   (`test_reward_defaults_are_the_v3_values_and_v4_is_explicit`,
   `test_c_disrupt_prices_a_blocked_legit_request_like_a_compromised_read`). Experience,
   val selection, rules tuning and every holdout policy run under the same reward. The
   rules were re-tuned under it, on train only.
2. **Detector blind to delegation grants.** The instrumentation now gets the business's
   grant table (`adversary.delegation_grants`: delegate principal → owners it may read),
   which is the operator's own authorization data. A read covered by a grant is not a
   cross-tenant attempt. A delegate's read outside its grant still is. This is
   `--delegation-aware-detector` / `LoopConfig.delegation_aware_detector`. Without the flag
   the gateway behaves as in v3. The generator's `is_attack` label is still never read
   (`test_detector_never_reads_the_generator_label`). Real effect: with no attack,
   `always_block_principal_long` drops from availability < 0.9 to 1.0
   (`test_aware_detector_removes_the_availability_cost_of_blanket_blocking`), and attackers
   and rogue delegates are still contained
   (`test_aware_detector_still_blocks_attackers_and_rogue_delegates`).
3. **Selection overfit one val scenario.** Snapshot, margin and round are now chosen on the
   unweighted mean over four val scenarios (`--val-selection scenario_mean`,
   `evaluate.scenario_mean_reward`): `val3_mixed` (copied unchanged) plus the new
   `val4_slow_insider`, `val4_rogue_delegate` and `val4_rotation_start` (seeds
   21000–23014, val band). Per-scenario val returns are recorded in the candidate manifest
   and the report.

`configs/live/promotion.yaml` is **unchanged**. DefenseSimEnv is untouched.

## Order of events (what was seen before the run)

1. Commit `0220e7d` (pushed before the run) contains the code, the reward value, `val_v4/`
   and `holdout_v4/`. `holdout_v4` consists of `payroll_rush`, `two_rogue_delegates` and
   `outsider_flood`, with seeds 43000–43029, 43500–43529 and 44000–44029. Its names and
   seeds are disjoint from every other split
   (`test_holdout_v4_is_new_and_disjoint_from_everything_else`).
2. Before the run the author ran only the unit tests. Those use tiny synthetic train/val
   scenarios. The v4 pipeline smoke test uses `train_v3`, `val_v4` (1 episode per
   scenario, a 20-update candidate) and the already exposed `holdout_v2`. No policy was run
   on `train_v3` or `val_v4` at full budget, and no hand-written policy was tried. This is
   unlike v3.
3. **No policy was evaluated on holdout_v4 before the final run.** The run evaluated every
   holdout_v4 episode once. Nothing was re-run or tuned.
4. After the run, only the run's own outputs were read (`promotion_report.json`,
   `candidate.manifest.json`). No further episodes were run.

## Verdict and interpretation

**`reject`**. Two of seven checks fail:

- **Availability floor: 0.847 < 0.85.** The miss is 0.003.
- **No-attack duty: 0.587 > 0.5.** In 59% of attack-free windows the candidate still blocked
  some legitimate request.

The other five pass. The paired gain over deployed is +7.89 [6.39, 9.34]. Compromise falls
from 1.00 to 0.145. False disruption is 0.139. The candidate beats the tuned rules (−7.85
vs −12.15) and does not regress on any held-out scenario (worst +2.87).

What the evidence says:

- **The fixes worked on what they targeted.** With the grant-aware detector, the
  availability floor is reachable while containing: `always_block_principal` gets 0.882
  availability at 0.21 compromise. In v3 every containing policy was at ≤ 0.52. The
  candidate's availability rose from 0.797 (v3) to 0.847. Val selection no longer sits at
  the grid edge: the selected margins were 0.5, 0.3 and 0.1 across rounds.
- **Where the duty and availability failures come from.** They come from
  `two_rogue_delegates` (availability 0.66, duty 0.79) and `outsider_flood` (0.84 / 0.67).
  On `payroll_rush` the candidate scores 0.96 / 0.26. When the attacker is also a legitimate
  user (a rogue bookkeeper, or a customer who attacks), blocking that principal blocks its
  own legitimate traffic too. Long blocks carry the block into the attack-free windows that
  follow. All long-block baselines show the same profile (`always_block_principal_long`
  0.836 / 0.606). Only short blocks (`always_block_principal` 0.882 / 0.334) stay inside both
  limits. The candidate prefers long blocks.
- **The candidate does not beat the trivial blocking baseline.** `always_block_principal`
  scores −7.31 against the candidate's −7.85; their confidence intervals overlap. Measured
  by the same thresholds (availability 0.882, duty 0.334, false disruption 0.083, above
  the rules and the deployed policy on every scenario), that fixed baseline would clear
  the gate's metric bars, while the learned candidate does not.
  The tuned rules are a weak bar on this holdout. Tuned on train, they use a hottest-node
  anomaly threshold of 0.2 that never fires on `payroll_rush`, so their compromise there is
  1.00. The gate compares against the tuned rules only, and that comparison is pre-registered;
  this report does not change it. Read the candidate's pass on `beats_static_rules`
  together with this baseline.
- **Training still degrades the value function.** In every round the best val snapshot was
  update 2000, the first one. In round 2, val return fell from −5.61 at 2000 updates to
  −15.28 at 16000. Longer offline training on 4–6k live transitions makes the warm-started
  Q-function worse, not better. This is the same symptom v3 diagnosed (sim-scale Q at the
  first snapshot). The margin and early stopping hide it rather than fix it. The candidate
  is effectively "the sim prior plus 2000 updates plus abstention".

The candidate came close but failed the pre-registered gate, and nothing was promoted.
Promotion would in any case need a human `usr_*` approver via `rl_defense.live.registry`.
Lab evidence only (RQ-005).

Open questions for humans (not acted on): whether the 0.5 duty cap and the 0.85 floor fit
scenarios where an attacker is also a legitimate user (blocking any such principal costs
its own traffic), and whether a learned policy is worth pursuing here given that short
blanket blocks with a grant-aware detector already match it.
