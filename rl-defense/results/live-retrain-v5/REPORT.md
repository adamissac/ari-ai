# Live retraining — held-out evaluation and promotion verdict

> Measured against the owned demo app (examples/payments-lite) in an isolated, in-process lab. Lab evidence only; not proof of real-world effectiveness (RQ-005).

**Decision: `reject`** (requires human approval: True).
Action space: `live_v3`; holdout scenarios from `configs/live/holdout_v5`.
Loop overrides: `{'c_disrupt': 1.0, 'delegation_aware_detector': True}`; val selection: `scenario_mean` over val3_mixed, val4_rogue_delegate, val4_rotation_start, val4_slow_insider.
Offline training: CQL penalty `cql_alpha=1.0`.
Deployed `b7cc2eceab4f` (sim-trained) vs candidate `fd2ecf22dfbc` (round 3, 6300 live transitions). Holdout: mixed_insiders, night_batch, token_spray × 30 episodes, paired.

## Held-out results (all scenarios)

| Policy | Return [95% CI] | Compromise | Availability | False disruption | No-attack duty | Actions/step |
|---|---|---|---|---|---|---|
| deployed | -15.74 [-17.16, -14.31] | 1.000 | 1.000 | 0.000 | 0.000 | 0.65 |
| candidate | -12.17 [-13.36, -11.01] | 0.675 | 0.991 | 0.010 | 0.045 | 0.50 |
| threshold_rules | -7.41 [-8.81, -6.01] | 0.279 | 0.958 | 0.040 | 0.216 | 0.09 |
| noop | -15.27 [-16.69, -13.84] | 1.000 | 1.000 | 0.000 | 0.000 | 0.00 |
| always_isolate_payments | -22.12 [-22.65, -21.56] | 0.000 | 0.357 | 0.642 | 1.000 | 0.33 |
| threshold_rules_no_block | -14.97 [-15.95, -13.90] | 0.155 | 0.646 | 0.182 | 0.296 | 0.22 |
| always_block_principal | -4.79 [-5.37, -4.19] | 0.133 | 0.924 | 0.038 | 0.198 | 0.20 |
| threshold_rules_short_only | -8.31 [-9.66, -6.92] | 0.368 | 0.976 | 0.019 | 0.105 | 0.12 |
| always_block_principal_long | -4.64 [-5.32, -3.96] | 0.065 | 0.897 | 0.084 | 0.413 | 0.11 |
| always_block_top_principal_long | -4.94 [-5.64, -4.23] | 0.097 | 0.903 | 0.076 | 0.406 | 0.13 |

Paired return gain (candidate − deployed): 3.57 [2.47, 4.75] over 90 episodes.

## Per held-out scenario (return / compromise / availability)

| Scenario | deployed | candidate | threshold_rules | noop | always_isolate_payments | threshold_rules_no_block | always_block_principal | threshold_rules_short_only | always_block_principal_long | always_block_top_principal_long |
|---|---|---|---|---|---|---|---|---|---|---|
| mixed_insiders | -10.93 / 1.00 / 1.00 | -10.38 / 0.93 / 0.99 | -6.83 / 0.39 / 0.92 | -10.40 / 1.00 / 1.00 | -20.64 / 0.00 / 0.38 | -13.31 / 0.33 / 0.70 | -5.98 / 0.33 / 0.92 | -8.00 / 0.62 / 0.95 | -5.60 / 0.15 / 0.88 | -6.50 / 0.29 / 0.90 |
| night_batch | -17.37 / 1.00 / 1.00 | -16.88 / 0.95 / 0.99 | -14.73 / 0.79 / 0.97 | -17.03 / 1.00 / 1.00 | -25.48 / 0.00 / 0.32 | -16.61 / 0.19 / 0.64 | -6.94 / 0.09 / 0.86 | -15.47 / 0.86 / 0.98 | -7.72 / 0.07 / 0.83 | -7.72 / 0.07 / 0.83 |
| token_spray | -18.92 / 1.00 / 1.00 | -9.26 / 0.46 / 0.99 | -0.66 / 0.03 / 1.00 | -18.37 / 1.00 / 1.00 | -20.23 / 0.00 / 0.37 | -14.97 / 0.07 / 0.57 | -1.44 / 0.07 / 1.00 | -1.47 / 0.07 / 1.00 | -0.61 / 0.03 / 1.00 | -0.61 / 0.03 / 1.00 |

## Acceptance criteria (pre-registered in configs/live/promotion.yaml)

| Check | Value | Threshold | Pass |
|---|---|---|---|
| paired_reward_gain_ci_low | 2.466 | > 0.0 | ✅ |
| compromise_rate_not_worse | 0.675 | <= 1.0 x deployed (1.000) | ✅ |
| availability_floor | 0.991 | >= 0.85 | ✅ |
| false_disruption_cap | 0.010 | <= 0.25 | ✅ |
| reward_hacking_no_blanket_isolation | 0.045 | <= 0.5 | ✅ |
| beats_static_rules | -12.171 | > rules (-7.407) | ❌ |
| no_per_scenario_regression | 0.495 | >= -0.0 | ✅ |

## Rounds (selection on validation only)

| Round | ε | New transitions | Selected update | Noop margin | Val return | Val compromise | Val availability |
|---|---|---|---|---|---|---|---|
| 1 | 0.5 | 2100 | 6000 | 0.3 | -15.09 | 0.893 | 0.989 |
| 2 | 0.3 | 2100 | 10000 | 0.0 | -14.81 | 0.860 | 0.984 |
| 3 | 0.2 | 2100 | 12000 | 0.0 | -14.28 | 0.834 | 0.985 |

Val return per scenario at each round's selected snapshot (the score above is their unweighted mean):

| Round | val3_mixed | val4_rogue_delegate | val4_rotation_start | val4_slow_insider |
|---|---|---|---|---|
| 1 | -15.23 | -13.14 | -16.87 | -15.13 |
| 2 | -15.53 | -12.31 | -16.54 | -14.86 |
| 3 | -14.18 | -12.69 | -15.84 | -14.41 |

Val return by number of offline updates (selection score; update 0 = warm start):

| Round | 0 | 2000 | 4000 | 6000 | 8000 | 10000 | 12000 | 14000 | 16000 |
|---|---|---|---|---|---|---|---|---|---|
| 1 | -15.85 | -15.81 | -15.21 | -15.09 | -15.25 | -15.18 | -15.34 | -15.29 | -15.68 |
| 2 | -15.85 | -15.47 | -15.17 | -14.99 | -14.84 | -14.81 | -14.87 | -15.20 | -15.31 |
| 3 | -15.85 | -15.52 | -14.76 | -14.55 | -14.41 | -14.39 | -14.28 | -14.44 | -14.63 |

Threshold rules tuned on train scenarios: `{'isolate_anomaly': 0.45, 'rate_limit_alerts': 1.1, 'monitor_anomaly': 1.1, 'block_anomaly': 0.2, 'block_min_volume': 0.0, 'long_mode': 'repeat', 'long_target': 'all'}`.
Best rules without `block_principal`: `{'isolate_anomaly': 0.15, 'rate_limit_alerts': 0.2, 'monitor_anomaly': 1.1}`.
Best rules with short blocks only: `{'isolate_anomaly': 0.45, 'rate_limit_alerts': 1.1, 'monitor_anomaly': 1.1, 'block_anomaly': 0.2}`.
