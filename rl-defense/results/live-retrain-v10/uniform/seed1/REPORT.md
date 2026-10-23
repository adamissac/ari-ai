# Live retraining — held-out evaluation and promotion verdict

> Measured against the owned demo app (examples/payments-lite) in an isolated, in-process lab. Lab evidence only; not proof of real-world effectiveness (RQ-005).

**Decision: `reject`** (requires human approval: True).
Action space: `live_v3`; holdout scenarios from `configs/live/holdout_v10`.
Loop overrides: `{'c_disrupt': 1.0, 'delegation_aware_detector': True, 'finding_severity_context': 'platform'}`; val selection: `scenario_mean` over val10_persistent, val10_quiet, val10_rotation.
Deployed `8113a37f4ff9` (sim-trained) vs candidate `f894c31834c5` (round 1, 139200 live transitions). Holdout: holdout10_persistent, holdout10_quiet, holdout10_rotation × 100 episodes, paired.

## Held-out results (all scenarios)

| Policy | Return [95% CI] | Compromise | Availability | False disruption | No-attack duty | Actions/step |
|---|---|---|---|---|---|---|
| deployed | -6.48 [-7.25, -5.78] | 0.132 | 0.872 | 0.099 | 0.287 | 0.69 |
| candidate | -6.21 [-6.99, -5.49] | 0.072 | 0.847 | 0.128 | 0.330 | 0.12 |
| threshold_rules | -6.19 [-6.97, -5.45] | 0.066 | 0.846 | 0.128 | 0.320 | 0.12 |
| noop | -14.45 [-15.59, -13.27] | 1.000 | 1.000 | 0.000 | 0.000 | 0.00 |
| always_isolate_payments | -22.15 [-22.44, -21.87] | 0.000 | 0.361 | 0.651 | 1.000 | 0.33 |
| always_block_principal | -5.45 [-6.10, -4.83] | 0.114 | 0.887 | 0.063 | 0.158 | 0.19 |
| always_block_principal_long | -6.23 [-7.01, -5.51] | 0.057 | 0.839 | 0.138 | 0.359 | 0.10 |
| always_block_top_principal_long | -6.20 [-6.97, -5.47] | 0.108 | 0.856 | 0.122 | 0.367 | 0.12 |
| random_valid | -16.19 [-16.73, -15.59] | 0.399 | 0.713 | 0.281 | 0.582 | 0.94 |
| v8 | -6.19 [-6.96, -5.47] | 0.070 | 0.845 | 0.132 | 0.345 | 0.12 |
| v9 | -6.19 [-6.96, -5.47] | 0.068 | 0.846 | 0.130 | 0.340 | 0.13 |

Paired return gain (candidate − deployed): 0.27 [0.11, 0.43] over 300 episodes.

## Per held-out scenario (return / compromise / availability)

| Scenario | deployed | candidate | threshold_rules | noop | always_isolate_payments | always_block_principal | always_block_principal_long | always_block_top_principal_long | random_valid | v8 | v9 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| holdout10_persistent | -0.97 / 0.02 / 1.00 | -0.34 / 0.01 / 1.00 | -0.34 / 0.01 / 1.00 | -24.65 / 1.00 / 1.00 | -19.24 / 0.00 / 0.41 | -1.20 / 0.04 / 1.00 | -0.28 / 0.01 / 1.00 | -0.28 / 0.01 / 1.00 | -16.04 / 0.33 / 0.78 | -0.32 / 0.01 / 1.00 | -0.34 / 0.01 / 1.00 |
| holdout10_quiet | -3.70 / 0.39 / 0.95 | -3.38 / 0.41 / 0.94 | -3.28 / 0.42 / 0.94 | -3.19 / 1.00 / 1.00 | -22.64 / 0.00 / 0.35 | -2.38 / 0.37 / 0.97 | -3.42 / 0.29 / 0.93 | -3.42 / 0.29 / 0.93 | -12.14 / 0.61 / 0.73 | -3.36 / 0.31 / 0.93 | -3.35 / 0.34 / 0.93 |
| holdout10_rotation | -14.78 / 0.22 / 0.70 | -14.92 / 0.10 / 0.64 | -14.94 / 0.09 / 0.63 | -15.51 / 1.00 / 1.00 | -24.56 / 0.00 / 0.33 | -12.77 / 0.16 / 0.72 | -14.97 / 0.09 / 0.63 | -14.90 / 0.19 / 0.67 | -20.38 / 0.45 / 0.65 | -14.90 / 0.11 / 0.64 | -14.87 / 0.10 / 0.64 |

## Acceptance criteria (pre-registered in configs/live/promotion.yaml)

| Check | Value | Threshold | Pass |
|---|---|---|---|
| paired_reward_gain_ci_low | 0.113 | > 0.0 | ✅ |
| compromise_rate_not_worse | 0.072 | <= 1.0 x deployed (0.132) | ✅ |
| availability_floor | 0.847 | >= 0.85 | ❌ |
| false_disruption_cap | 0.128 | <= 0.25 | ✅ |
| reward_hacking_no_blanket_isolation | 0.330 | <= 0.5 | ✅ |
| beats_static_rules | -6.214 | > rules (-6.187) | ❌ |
| no_per_scenario_regression | -0.142 | >= -0.0 | ❌ |

## Online training (selection on validation only; one run, columns in env steps)

| Round | ε | New transitions | Selected update | Noop margin | Val return | Val compromise | Val availability |
|---|---|---|---|---|---|---|---|
| 1 | 0.3->0.05 | 135000 | 135000 | 0.5 | -6.70 | 0.058 | 0.831 |

Val return per scenario at each round's selected snapshot (the score above is their unweighted mean):

| Round | val10_persistent | val10_quiet | val10_rotation |
|---|---|---|---|
| 1 | -0.23 | -3.27 | -16.60 |

Val return by environment steps (selection score; step 0 = after demonstration pretraining):

| Round | 0 | 15000 | 30000 | 45000 | 60000 | 75000 | 90000 | 105000 | 120000 | 135000 | 150000 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | -6.78 | -6.78 | -6.78 | -6.78 | -6.76 | -6.78 | -6.74 | -6.75 | -6.78 | -6.70 | -6.75 |

Threshold rules tuned on train scenarios: `{'isolate_anomaly': 0.45, 'rate_limit_alerts': 1.1, 'monitor_anomaly': 1.1, 'block_anomaly': 0.1, 'block_min_volume': 0.0, 'long_mode': 'repeat', 'long_target': 'all'}`.

## Demonstrations and online schedule

Expert (chosen on train only): `threshold_rules`. Train returns: threshold_rules -3.65, always_block_principal -4.80, always_block_principal_long -3.94, always_block_top_principal_long -3.94.
Demonstrations: 4200 transitions (20 episodes per train scenario); pretraining 5000 updates; online 135000 live transitions, ε 0.3→0.05 over 75000 steps, demo share 0.25 of every batch, DQfD λ=1.0, margin 0.8. Fresh network (no simulator prior).
Selected: env step 135000, noop margin 0.5.

Paired return (candidate − expert `threshold_rules`) on holdout: -0.03 [-0.09, 0.04] over 300 episodes.

Finding-severity context: `platform` (drawn per episode from the severities platform_mapping can produce; every policy, every split).

Reference (reported only, not in the gate) `v8`: `results/live-retrain-v8/candidate_online.pt` (`ec8b5042fd56`). Paired return (candidate − v8) on holdout: -0.02 [-0.07, 0.02] over 300 episodes.

Reference (reported only, not in the gate) `v9`: `results/live-retrain-v9/seed1/candidate_online.pt` (`df00788a6c3e`). Paired return (candidate − v9) on holdout: -0.03 [-0.08, 0.02] over 300 episodes.
