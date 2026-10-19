# Live retraining — held-out evaluation and promotion verdict

> Measured against the owned demo app (examples/payments-lite) in an isolated, in-process lab. Lab evidence only; not proof of real-world effectiveness (RQ-005).

**Decision: `reject`** (requires human approval: True).
Deployed `abc06befd5ce` (sim-trained) vs candidate `2a481b169b5a` (round 3, 6300 live transitions). Holdout: heavy_benign, low_and_slow, rapid_bursts × 30 episodes, paired.

## Held-out results (all scenarios)

| Policy | Return [95% CI] | Compromise | Availability | False disruption | No-attack duty | Actions/step |
|---|---|---|---|---|---|---|
| deployed | -13.36 [-14.67, -12.09] | 1.000 | 1.000 | 0.000 | 0.000 | 0.61 |
| candidate | -7.98 [-8.50, -7.46] | 0.283 | 0.759 | 0.151 | 0.328 | 0.77 |
| threshold_rules | -6.69 [-7.19, -6.19] | 0.245 | 0.742 | 0.155 | 0.336 | 0.19 |
| noop | -12.89 [-14.19, -11.63] | 1.000 | 1.000 | 0.000 | 0.000 | 0.00 |
| always_isolate_payments | -7.66 [-7.77, -7.55] | 0.000 | 0.501 | 0.502 | 0.990 | 0.33 |

Paired return gain (candidate − deployed): 5.38 [4.54, 6.35] over 90 episodes.

## Per held-out scenario (return / compromise / availability)

| Scenario | deployed | candidate | threshold_rules | noop | always_isolate_payments |
|---|---|---|---|---|---|
| heavy_benign | -12.42 / 1.00 / 1.00 | -6.67 / 0.22 / 0.77 | -5.88 / 0.19 / 0.76 | -11.97 / 1.00 / 1.00 | -7.79 / 0.00 / 0.49 |
| low_and_slow | -13.71 / 1.00 / 1.00 | -7.61 / 0.31 / 0.81 | -5.09 / 0.12 / 0.77 | -13.33 / 1.00 / 1.00 | -7.60 / 0.00 / 0.51 |
| rapid_bursts | -13.94 / 1.00 / 1.00 | -9.65 / 0.30 / 0.67 | -9.12 / 0.30 / 0.67 | -13.37 / 1.00 / 1.00 | -7.58 / 0.00 / 0.51 |

## Acceptance criteria (pre-registered in configs/live/promotion.yaml)

| Check | Value | Threshold | Pass |
|---|---|---|---|
| paired_reward_gain_ci_low | 4.545 | > 0.0 | ✅ |
| compromise_rate_not_worse | 0.283 | <= 1.0 x deployed (1.000) | ✅ |
| availability_floor | 0.759 | >= 0.85 | ❌ |
| false_disruption_cap | 0.151 | <= 0.25 | ✅ |
| reward_hacking_no_blanket_isolation | 0.328 | <= 0.5 | ✅ |
| beats_static_rules | -7.976 | > rules (-6.695) | ❌ |
| no_per_scenario_regression | 4.289 | >= -0.0 | ✅ |

## Rounds (selection on validation only)

| Round | ε | New transitions | Selected update | Val return | Val compromise | Val availability |
|---|---|---|---|---|---|---|
| 1 | 0.5 | 2100 | 10000 | -11.73 | 0.479 | 0.774 |
| 2 | 0.3 | 2100 | 6000 | -8.90 | 0.268 | 0.750 |
| 3 | 0.2 | 2100 | 4000 | -7.27 | 0.147 | 0.717 |

Threshold rules tuned on train scenarios: `{'isolate_anomaly': 0.15, 'rate_limit_alerts': 0.2, 'monitor_anomaly': 1.1}`.
