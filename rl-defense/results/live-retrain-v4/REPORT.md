# Live retraining — held-out evaluation and promotion verdict

> Measured against the owned demo app (examples/payments-lite) in an isolated, in-process lab. Lab evidence only; not proof of real-world effectiveness (RQ-005).

**Decision: `reject`** (requires human approval: True).
Action space: `live_v3`; holdout scenarios from `configs/live/holdout_v4`.
Loop overrides: `{'c_disrupt': 1.0, 'delegation_aware_detector': True}`; val selection: `scenario_mean` over val3_mixed, val4_rogue_delegate, val4_rotation_start, val4_slow_insider.
Deployed `6c130629506c` (sim-trained) vs candidate `0389c820a4a2` (round 2, 4200 live transitions). Holdout: outsider_flood, payroll_rush, two_rogue_delegates × 30 episodes, paired.

## Held-out results (all scenarios)

| Policy | Return [95% CI] | Compromise | Availability | False disruption | No-attack duty | Actions/step |
|---|---|---|---|---|---|---|
| deployed | -15.74 [-16.95, -14.47] | 1.000 | 1.000 | 0.000 | 0.000 | 0.57 |
| candidate | -7.85 [-8.76, -6.96] | 0.145 | 0.847 | 0.139 | 0.587 | 0.33 |
| threshold_rules | -12.15 [-13.38, -10.92] | 0.269 | 0.862 | 0.133 | 0.498 | 0.09 |
| noop | -15.30 [-16.51, -14.03] | 1.000 | 1.000 | 0.000 | 0.000 | 0.00 |
| always_isolate_payments | -21.76 [-22.74, -20.85] | 0.000 | 0.355 | 0.643 | 1.000 | 0.33 |
| threshold_rules_no_block | -15.26 [-16.26, -14.20] | 0.240 | 0.680 | 0.186 | 0.346 | 0.21 |
| always_block_principal | -7.31 [-8.18, -6.50] | 0.208 | 0.882 | 0.083 | 0.334 | 0.22 |
| threshold_rules_short_only | -12.15 [-13.42, -10.88] | 0.397 | 0.906 | 0.073 | 0.282 | 0.14 |
| always_block_principal_long | -7.48 [-8.37, -6.63] | 0.090 | 0.836 | 0.153 | 0.606 | 0.12 |
| always_block_top_principal_long | -7.79 [-8.67, -6.91] | 0.179 | 0.852 | 0.134 | 0.593 | 0.16 |

Paired return gain (candidate − deployed): 7.89 [6.39, 9.34] over 90 episodes.

## Per held-out scenario (return / compromise / availability)

| Scenario | deployed | candidate | threshold_rules | noop | always_isolate_payments | threshold_rules_no_block | always_block_principal | threshold_rules_short_only | always_block_principal_long | always_block_top_principal_long |
|---|---|---|---|---|---|---|---|---|---|---|
| outsider_flood | -14.62 / 1.00 / 1.00 | -7.97 / 0.18 / 0.84 | -7.35 / 0.11 / 0.81 | -14.10 / 1.00 / 1.00 | -17.42 / 0.00 / 0.44 | -12.96 / 0.22 / 0.68 | -7.30 / 0.23 / 0.87 | -7.35 / 0.23 / 0.87 | -7.21 / 0.10 / 0.81 | -8.18 / 0.24 / 0.85 |
| payroll_rush | -17.00 / 1.00 / 1.00 | -2.86 / 0.07 / 0.96 | -16.73 / 1.00 / 1.00 | -16.73 / 1.00 / 1.00 | -27.66 / 0.00 / 0.28 | -16.98 / 0.38 / 0.72 | -2.84 / 0.09 / 0.97 | -16.73 / 1.00 / 1.00 | -2.68 / 0.07 / 0.96 | -2.68 / 0.07 / 0.96 |
| two_rogue_delegates | -15.58 / 1.00 / 1.00 | -12.71 / 0.12 / 0.66 | -12.37 / 0.16 / 0.69 | -15.07 / 1.00 / 1.00 | -20.20 / 0.00 / 0.37 | -15.84 / 0.21 / 0.60 | -11.81 / 0.24 / 0.74 | -12.38 / 0.37 / 0.79 | -12.56 / 0.08 / 0.65 | -12.52 / 0.12 / 0.66 |

## Acceptance criteria (pre-registered in configs/live/promotion.yaml)

| Check | Value | Threshold | Pass |
|---|---|---|---|
| paired_reward_gain_ci_low | 6.388 | > 0.0 | ✅ |
| compromise_rate_not_worse | 0.145 | <= 1.0 x deployed (1.000) | ✅ |
| availability_floor | 0.847 | >= 0.85 | ❌ |
| false_disruption_cap | 0.139 | <= 0.25 | ✅ |
| reward_hacking_no_blanket_isolation | 0.587 | <= 0.5 | ❌ |
| beats_static_rules | -7.849 | > rules (-12.153) | ✅ |
| no_per_scenario_regression | 2.873 | >= -0.0 | ✅ |

## Rounds (selection on validation only)

| Round | ε | New transitions | Selected update | Noop margin | Val return | Val compromise | Val availability |
|---|---|---|---|---|---|---|---|
| 1 | 0.5 | 2100 | 2000 | 0.5 | -5.84 | 0.151 | 0.914 |
| 2 | 0.3 | 2100 | 2000 | 0.3 | -5.61 | 0.160 | 0.913 |
| 3 | 0.2 | 2100 | 2000 | 0.1 | -5.74 | 0.151 | 0.910 |

Val return per scenario at each round's selected snapshot (the score above is their unweighted mean):

| Round | val3_mixed | val4_rogue_delegate | val4_rotation_start | val4_slow_insider |
|---|---|---|---|---|
| 1 | -5.43 | -8.13 | -6.07 | -3.74 |
| 2 | -4.98 | -7.79 | -6.27 | -3.40 |
| 3 | -5.44 | -7.09 | -6.81 | -3.63 |

Threshold rules tuned on train scenarios: `{'isolate_anomaly': 0.45, 'rate_limit_alerts': 1.1, 'monitor_anomaly': 1.1, 'block_anomaly': 0.2, 'block_min_volume': 0.0, 'long_mode': 'repeat', 'long_target': 'all'}`.
Best rules without `block_principal`: `{'isolate_anomaly': 0.15, 'rate_limit_alerts': 0.2, 'monitor_anomaly': 1.1}`.
Best rules with short blocks only: `{'isolate_anomaly': 0.45, 'rate_limit_alerts': 1.1, 'monitor_anomaly': 1.1, 'block_anomaly': 0.2}`.
