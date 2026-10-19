# Live retraining — held-out evaluation and promotion verdict

> Measured against the owned demo app (examples/payments-lite) in an isolated, in-process lab. Lab evidence only; not proof of real-world effectiveness (RQ-005).

**Decision: `reject`** (requires human approval: True).
Action space: `live_v3`; holdout scenarios from `configs/live/holdout_v3`.
Deployed `0c5b7d06e7f7` (sim-trained) vs candidate `99942950bd98` (round 3, 6300 live transitions). Holdout: heavy_reconciliation, rogue_bookkeeper, three_identities_delegated × 30 episodes, paired.

## Held-out results (all scenarios)

| Policy | Return [95% CI] | Compromise | Availability | False disruption | No-attack duty | Actions/step |
|---|---|---|---|---|---|---|
| deployed | -15.88 [-17.08, -14.78] | 1.000 | 1.000 | 0.000 | 0.000 | 0.99 |
| candidate | -13.87 [-15.35, -12.50] | 0.657 | 0.797 | 0.187 | 0.622 | 0.20 |
| threshold_rules | -10.98 [-11.40, -10.56] | 0.185 | 0.491 | 0.462 | 0.827 | 0.40 |
| noop | -15.29 [-16.48, -14.19] | 1.000 | 1.000 | 0.000 | 0.000 | 0.00 |
| always_isolate_payments | -10.99 [-11.26, -10.69] | 0.000 | 0.337 | 0.663 | 1.000 | 0.33 |
| threshold_rules_no_block | -10.79 [-11.08, -10.47] | 0.183 | 0.492 | 0.447 | 0.676 | 0.29 |
| always_block_principal | -12.08 [-12.79, -11.39] | 0.261 | 0.500 | 0.481 | 1.000 | 0.48 |
| threshold_rules_short_only | -10.79 [-11.08, -10.47] | 0.183 | 0.492 | 0.447 | 0.676 | 0.29 |
| always_block_principal_long | -10.61 [-11.28, -9.95] | 0.145 | 0.486 | 0.503 | 1.000 | 0.24 |
| always_block_top_principal_long | -11.13 [-11.70, -10.58] | 0.214 | 0.521 | 0.485 | 0.995 | 0.33 |

Paired return gain (candidate − deployed): 2.01 [0.94, 3.06] over 90 episodes.

## Per held-out scenario (return / compromise / availability)

| Scenario | deployed | candidate | threshold_rules | noop | always_isolate_payments | threshold_rules_no_block | always_block_principal | threshold_rules_short_only | always_block_principal_long | always_block_top_principal_long |
|---|---|---|---|---|---|---|---|---|---|---|
| heavy_reconciliation | -16.23 / 1.00 / 1.00 | -19.84 / 0.89 / 0.68 | -12.79 / 0.12 / 0.39 | -15.63 / 1.00 / 1.00 | -12.51 / 0.00 / 0.30 | -11.62 / 0.07 / 0.41 | -11.19 / 0.09 / 0.46 | -11.62 / 0.07 / 0.41 | -10.81 / 0.07 / 0.45 | -11.97 / 0.16 / 0.47 |
| rogue_bookkeeper | -14.26 / 1.00 / 1.00 | -9.02 / 0.52 / 0.88 | -9.20 / 0.21 / 0.59 | -13.67 / 1.00 / 1.00 | -9.35 / 0.00 / 0.39 | -10.11 / 0.28 / 0.59 | -8.70 / 0.16 / 0.59 | -10.11 / 0.28 / 0.59 | -6.79 / 0.03 / 0.59 | -8.43 / 0.16 / 0.59 |
| three_identities_delegated | -17.16 / 1.00 / 1.00 | -12.76 / 0.66 / 0.91 | -10.97 / 0.20 / 0.55 | -16.57 / 1.00 / 1.00 | -11.10 / 0.00 / 0.35 | -10.64 / 0.16 / 0.53 | -16.35 / 0.45 / 0.50 | -10.64 / 0.16 / 0.53 | -14.23 / 0.30 / 0.46 | -13.00 / 0.30 / 0.53 |

## Acceptance criteria (pre-registered in configs/live/promotion.yaml)

| Check | Value | Threshold | Pass |
|---|---|---|---|
| paired_reward_gain_ci_low | 0.941 | > 0.0 | ✅ |
| compromise_rate_not_worse | 0.657 | <= 1.0 x deployed (1.000) | ✅ |
| availability_floor | 0.797 | >= 0.85 | ❌ |
| false_disruption_cap | 0.187 | <= 0.25 | ✅ |
| reward_hacking_no_blanket_isolation | 0.622 | <= 0.5 | ❌ |
| beats_static_rules | -13.875 | > rules (-10.985) | ❌ |
| no_per_scenario_regression | -3.617 | >= -0.0 | ❌ |

## Rounds (selection on validation only)

| Round | ε | New transitions | Selected update | Noop margin | Val return | Val compromise | Val availability |
|---|---|---|---|---|---|---|---|
| 1 | 0.5 | 2100 | 2000 | 0.5 | -9.40 | 0.230 | 0.681 |
| 2 | 0.3 | 2100 | 4000 | 0.5 | -7.72 | 0.434 | 0.944 |
| 3 | 0.2 | 2100 | 8000 | 0.5 | -7.21 | 0.418 | 0.963 |

Threshold rules tuned on train scenarios: `{'isolate_anomaly': 0.3, 'rate_limit_alerts': 0.6, 'monitor_anomaly': 1.1, 'block_anomaly': 0.35, 'block_min_volume': 0.2, 'long_mode': 'always', 'long_target': 'top'}`.
Best rules without `block_principal`: `{'isolate_anomaly': 0.3, 'rate_limit_alerts': 0.6, 'monitor_anomaly': 1.1}`.
Best rules with short blocks only: `{'isolate_anomaly': 0.3, 'rate_limit_alerts': 0.6, 'monitor_anomaly': 1.1, 'block_anomaly': 0.5}`.
