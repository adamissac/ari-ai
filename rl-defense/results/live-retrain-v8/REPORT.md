# Live retraining — held-out evaluation and promotion verdict

> Measured against the owned demo app (examples/payments-lite) in an isolated, in-process lab. Lab evidence only; not proof of real-world effectiveness (RQ-005).

**Decision: `recommend_promote`** (requires human approval: True).
Action space: `live_v3`; holdout scenarios from `configs/live/holdout_v8`.
Loop overrides: `{'c_disrupt': 1.0, 'delegation_aware_detector': True, 'finding_severity_context': 'platform'}`; val selection: `scenario_mean` over val3_mixed, val4_rogue_delegate, val4_rotation_start, val4_slow_insider.
Deployed `cea15d7cd6f9` (sim-trained) vs candidate `ec8b5042fd56` (round 1, 109200 live transitions). Holdout: faint_outsider_campaigns, insider_pair_windows, rare_bookkeeper_raids × 30 episodes, paired.

## Held-out results (all scenarios)

| Policy | Return [95% CI] | Compromise | Availability | False disruption | No-attack duty | Actions/step |
|---|---|---|---|---|---|---|
| deployed | -10.33 [-11.76, -8.87] | 1.000 | 0.984 | 0.016 | 0.043 | 0.64 |
| candidate | -5.86 [-6.89, -4.81] | 0.345 | 0.917 | 0.072 | 0.291 | 0.12 |
| threshold_rules | -6.46 [-7.37, -5.54] | 0.308 | 0.911 | 0.076 | 0.297 | 0.11 |
| noop | -9.22 [-10.62, -7.76] | 1.000 | 1.000 | 0.000 | 0.000 | 0.00 |
| always_isolate_payments | -20.51 [-21.03, -20.01] | 0.000 | 0.385 | 0.622 | 1.000 | 0.33 |
| always_block_principal | -5.61 [-6.76, -4.48] | 0.553 | 0.950 | 0.035 | 0.148 | 0.16 |
| always_block_principal_long | -5.16 [-6.09, -4.25] | 0.205 | 0.901 | 0.087 | 0.339 | 0.10 |
| always_block_top_principal_long | -5.16 [-6.09, -4.25] | 0.205 | 0.901 | 0.087 | 0.339 | 0.10 |
| v6 | -5.94 [-6.99, -4.92] | 0.394 | 0.929 | 0.061 | 0.252 | 0.75 |
| v7 | -5.40 [-6.50, -4.32] | 0.436 | 0.932 | 0.058 | 0.256 | 0.11 |

Paired return gain (candidate − deployed): 4.47 [3.14, 5.81] over 90 episodes.

## Per held-out scenario (return / compromise / availability)

| Scenario | deployed | candidate | threshold_rules | noop | always_isolate_payments | always_block_principal | always_block_principal_long | always_block_top_principal_long | v6 | v7 |
|---|---|---|---|---|---|---|---|---|---|---|
| faint_outsider_campaigns | -13.17 / 1.00 / 0.98 | -2.83 / 0.23 / 1.00 | -4.97 / 0.41 / 1.00 | -12.03 / 1.00 / 1.00 | -19.76 / 0.00 / 0.40 | -1.72 / 0.14 / 1.00 | -1.25 / 0.10 / 1.00 | -1.25 / 0.10 / 1.00 | -2.05 / 0.12 / 1.00 | -1.26 / 0.10 / 1.00 |
| insider_pair_windows | -14.29 / 1.00 / 0.98 | -11.71 / 0.36 / 0.78 | -11.40 / 0.28 / 0.76 | -13.13 / 1.00 / 1.00 | -18.29 / 0.00 / 0.42 | -12.66 / 0.63 / 0.87 | -10.62 / 0.21 / 0.75 | -10.62 / 0.21 / 0.75 | -12.08 / 0.43 / 0.81 | -12.05 / 0.50 / 0.83 |
| rare_bookkeeper_raids | -3.55 / 1.00 / 0.99 | -3.03 / 0.40 / 0.94 | -2.99 / 0.40 / 0.94 | -2.50 / 1.00 / 1.00 | -23.47 / 0.00 / 0.34 | -2.44 / 0.51 / 0.97 | -3.61 / 0.35 / 0.92 | -3.61 / 0.35 / 0.92 | -3.70 / 0.53 / 0.95 | -2.87 / 0.41 / 0.95 |

## Acceptance criteria (pre-registered in configs/live/promotion.yaml)

| Check | Value | Threshold | Pass |
|---|---|---|---|
| paired_reward_gain_ci_low | 3.144 | > 0.0 | ✅ |
| compromise_rate_not_worse | 0.345 | <= 1.0 x deployed (1.000) | ✅ |
| availability_floor | 0.917 | >= 0.85 | ✅ |
| false_disruption_cap | 0.072 | <= 0.25 | ✅ |
| reward_hacking_no_blanket_isolation | 0.291 | <= 0.5 | ✅ |
| beats_static_rules | -5.860 | > rules (-6.456) | ✅ |
| no_per_scenario_regression | 0.511 | >= -0.0 | ✅ |

## Online training (selection on validation only; one run, columns in env steps)

| Round | ε | New transitions | Selected update | Noop margin | Val return | Val compromise | Val availability |
|---|---|---|---|---|---|---|---|
| 1 | 0.3->0.05 | 105000 | 105000 | 0.0 | -6.74 | 0.265 | 0.914 |

Val return per scenario at each round's selected snapshot (the score above is their unweighted mean):

| Round | val3_mixed | val4_rogue_delegate | val4_rotation_start | val4_slow_insider |
|---|---|---|---|---|
| 1 | -6.93 | -6.77 | -9.97 | -3.29 |

Val return by environment steps (selection score; step 0 = after demonstration pretraining):

| Round | 0 | 15000 | 30000 | 45000 | 60000 | 75000 | 90000 | 105000 | 120000 | 135000 | 150000 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | -7.03 | -7.04 | -7.04 | -7.01 | -7.02 | -7.06 | -6.86 | -6.74 | -6.79 | -6.83 | -6.92 |

Threshold rules tuned on train scenarios: `{'isolate_anomaly': 0.45, 'rate_limit_alerts': 1.1, 'monitor_anomaly': 1.1, 'block_anomaly': 0.1, 'block_min_volume': 0.0, 'long_mode': 'repeat', 'long_target': 'all'}`.

## Demonstrations and online schedule

Expert (chosen on train only): `threshold_rules`. Train returns: threshold_rules -3.65, always_block_principal -4.80, always_block_principal_long -3.94, always_block_top_principal_long -3.94.
Demonstrations: 4200 transitions (20 episodes per train scenario); pretraining 5000 updates; online 105000 live transitions, ε 0.3→0.05 over 75000 steps, demo share 0.25 of every batch, DQfD λ=1.0, margin 0.8. Fresh network (no simulator prior).
Selected: env step 105000, noop margin 0.0.

Paired return (candidate − expert `threshold_rules`) on holdout: 0.60 [0.08, 1.17] over 90 episodes.

Finding-severity context: `platform` (drawn per episode from the severities platform_mapping can produce; every policy, every split).

Reference (reported only, not in the gate) `v6`: `results/live-retrain-v6/candidate_online.pt` (`8113a37f4ff9`). Paired return (candidate − v6) on holdout: 0.08 [-0.40, 0.50] over 90 episodes.

Reference (reported only, not in the gate) `v7`: `results/live-retrain-v7/candidate_online.pt` (`d1c0c9b506fd`). Paired return (candidate − v7) on holdout: -0.46 [-0.96, -0.07] over 90 episodes.
