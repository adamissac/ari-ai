# Live retraining — held-out evaluation and promotion verdict

> Measured against the owned demo app (examples/payments-lite) in an isolated, in-process lab. Lab evidence only; not proof of real-world effectiveness (RQ-005).

**Decision: `reject`** (requires human approval: True).
Action space: `live_v2`; holdout scenarios from `configs/live/holdout_v2`.
Deployed `967e4fcbf2d7` (sim-trained) vs candidate `6993f1b06fdb` (round 3, 6300 live transitions). Holdout: outsider_and_insider, token_rotation, two_identities × 30 episodes, paired.

## Held-out results (all scenarios)

| Policy | Return [95% CI] | Compromise | Availability | False disruption | No-attack duty | Actions/step |
|---|---|---|---|---|---|---|
| deployed | -14.58 [-15.66, -13.52] | 1.000 | 1.000 | 0.000 | 0.000 | 0.74 |
| candidate | -7.29 [-8.09, -6.56] | 0.373 | 0.889 | 0.079 | 0.319 | 0.67 |
| threshold_rules | -6.96 [-7.77, -6.25] | 0.373 | 0.889 | 0.079 | 0.319 | 0.23 |
| noop | -14.03 [-15.10, -12.99] | 1.000 | 1.000 | 0.000 | 0.000 | 0.00 |
| always_isolate_payments | -7.63 [-7.73, -7.52] | 0.000 | 0.505 | 0.497 | 0.994 | 0.33 |
| threshold_rules_no_block | -7.44 [-7.80, -7.05] | 0.222 | 0.711 | 0.200 | 0.383 | 0.20 |
| always_block_principal | -6.96 [-7.77, -6.25] | 0.373 | 0.889 | 0.079 | 0.319 | 0.23 |

Paired return gain (candidate − deployed): 7.30 [6.27, 8.39] over 90 episodes.

## Per held-out scenario (return / compromise / availability)

| Scenario | deployed | candidate | threshold_rules | noop | always_isolate_payments | threshold_rules_no_block | always_block_principal |
|---|---|---|---|---|---|---|---|
| outsider_and_insider | -16.43 / 1.00 / 1.00 | -5.49 / 0.22 / 0.90 | -5.18 / 0.22 / 0.90 | -15.90 / 1.00 / 1.00 | -7.58 / 0.00 / 0.51 | -8.21 / 0.21 / 0.68 | -5.18 / 0.22 / 0.90 |
| token_rotation | -12.03 / 1.00 / 1.00 | -4.33 / 0.23 / 0.92 | -3.98 / 0.23 / 0.92 | -11.50 / 1.00 / 1.00 | -7.63 / 0.00 / 0.50 | -6.28 / 0.23 / 0.77 | -3.98 / 0.23 / 0.92 |
| two_identities | -15.28 / 1.00 / 1.00 | -12.03 / 0.64 / 0.86 | -11.73 / 0.64 / 0.86 | -14.70 / 1.00 / 1.00 | -7.68 / 0.00 / 0.50 | -7.81 / 0.22 / 0.71 | -11.73 / 0.64 / 0.86 |

## Acceptance criteria (pre-registered in configs/live/promotion.yaml)

| Check | Value | Threshold | Pass |
|---|---|---|---|
| paired_reward_gain_ci_low | 6.271 | > 0.0 | ✅ |
| compromise_rate_not_worse | 0.373 | <= 1.0 x deployed (1.000) | ✅ |
| availability_floor | 0.889 | >= 0.85 | ✅ |
| false_disruption_cap | 0.079 | <= 0.25 | ✅ |
| reward_hacking_no_blanket_isolation | 0.319 | <= 0.5 | ✅ |
| beats_static_rules | -7.285 | > rules (-6.961) | ❌ |
| no_per_scenario_regression | 3.251 | >= -0.0 | ✅ |

## Rounds (selection on validation only)

| Round | ε | New transitions | Selected update | Val return | Val compromise | Val availability |
|---|---|---|---|---|---|---|
| 1 | 0.5 | 2100 | 2000 | -6.03 | 0.186 | 0.849 |
| 2 | 0.3 | 2100 | 2000 | -5.72 | 0.186 | 0.870 |
| 3 | 0.2 | 2100 | 2000 | -4.93 | 0.147 | 0.862 |

Threshold rules tuned on train scenarios: `{'isolate_anomaly': 0.6, 'rate_limit_alerts': 1.1, 'monitor_anomaly': 1.1, 'block_anomaly': 0.1}`.
Best rules without `block_principal`: `{'isolate_anomaly': 0.15, 'rate_limit_alerts': 0.2, 'monitor_anomaly': 1.1}`.
