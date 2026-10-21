# Live retraining — held-out evaluation and promotion verdict

> Measured against the owned demo app (examples/payments-lite) in an isolated, in-process lab. Lab evidence only; not proof of real-world effectiveness (RQ-005).

**Decision: `reject`** (requires human approval: True).
Action space: `live_v3`; holdout scenarios from `configs/live/holdout_v9`.
Loop overrides: `{'c_disrupt': 1.0, 'delegation_aware_detector': True, 'finding_severity_context': 'platform'}`; val selection: `scenario_mean` over val3_mixed, val4_rogue_delegate, val4_rotation_start, val4_slow_insider, val9_faint_outsider, val9_quiet_delegate.
Deployed `8113a37f4ff9` (sim-trained) vs candidate `df00788a6c3e` (round 1, 154200 live transitions). Holdout: faint_outsider_reconciliation, mixed_delegate_rotation, quiet_rogue_reconciler × 100 episodes, paired.

## Held-out results (all scenarios)

| Policy | Return [95% CI] | Compromise | Availability | False disruption | No-attack duty | Actions/step |
|---|---|---|---|---|---|---|
| deployed | -5.66 [-6.30, -5.03] | 0.273 | 0.917 | 0.059 | 0.195 | 0.63 |
| candidate | -5.65 [-6.34, -5.00] | 0.202 | 0.899 | 0.076 | 0.235 | 0.09 |
| threshold_rules | -7.44 [-8.21, -6.74] | 0.279 | 0.900 | 0.073 | 0.205 | 0.05 |
| noop | -6.74 [-7.45, -6.05] | 1.000 | 1.000 | 0.000 | 0.000 | 0.00 |
| always_isolate_payments | -24.53 [-24.71, -24.34] | 0.000 | 0.337 | 0.663 | 1.000 | 0.33 |
| always_block_principal | -4.73 [-5.32, -4.19] | 0.280 | 0.930 | 0.041 | 0.124 | 0.10 |
| always_block_principal_long | -5.86 [-6.57, -5.19] | 0.153 | 0.884 | 0.092 | 0.276 | 0.07 |
| always_block_top_principal_long | -5.76 [-6.46, -5.08] | 0.193 | 0.891 | 0.086 | 0.277 | 0.08 |
| random_valid | -14.05 [-14.61, -13.50] | 0.533 | 0.734 | 0.259 | 0.556 | 0.94 |
| v7 | -5.21 [-5.89, -4.59] | 0.330 | 0.924 | 0.054 | 0.169 | 0.07 |
| v8 | -5.87 [-6.56, -5.21] | 0.220 | 0.900 | 0.075 | 0.232 | 0.08 |

Paired return gain (candidate − deployed): 0.00 [-0.19, 0.19] over 300 episodes.

## Per held-out scenario (return / compromise / availability)

| Scenario | deployed | candidate | threshold_rules | noop | always_isolate_payments | always_block_principal | always_block_principal_long | always_block_top_principal_long | random_valid | v7 | v8 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| faint_outsider_reconciliation | -1.86 / 0.18 / 1.00 | -1.69 / 0.22 / 1.00 | -7.25 / 0.97 / 1.00 | -7.47 / 1.00 / 1.00 | -25.65 / 0.00 / 0.33 | -1.59 / 0.20 / 1.00 | -1.18 / 0.15 / 1.00 | -1.18 / 0.15 / 1.00 | -12.53 / 0.45 / 0.78 | -1.43 / 0.18 / 1.00 | -2.45 / 0.32 / 1.00 |
| mixed_delegate_rotation | -12.71 / 0.27 / 0.74 | -13.09 / 0.18 / 0.69 | -13.37 / 0.14 / 0.67 | -11.30 / 1.00 / 1.00 | -23.50 / 0.00 / 0.34 | -10.99 / 0.27 / 0.78 | -13.79 / 0.13 / 0.65 | -13.46 / 0.18 / 0.68 | -18.24 / 0.54 / 0.68 | -12.41 / 0.33 / 0.76 | -12.97 / 0.19 / 0.69 |
| quiet_rogue_reconciler | -2.40 / 0.61 / 0.97 | -2.18 / 0.51 / 0.96 | -1.69 / 0.71 / 0.98 | -1.44 / 1.00 / 1.00 | -24.44 / 0.00 / 0.34 | -1.61 / 0.57 / 0.98 | -2.63 / 0.48 / 0.95 | -2.63 / 0.48 / 0.95 | -11.39 / 0.67 / 0.74 | -1.80 / 0.71 / 0.98 | -2.18 / 0.50 / 0.96 |

## Acceptance criteria (pre-registered in configs/live/promotion.yaml)

| Check | Value | Threshold | Pass |
|---|---|---|---|
| paired_reward_gain_ci_low | -0.188 | > 0.0 | ❌ |
| compromise_rate_not_worse | 0.202 | <= 1.0 x deployed (0.273) | ✅ |
| availability_floor | 0.899 | >= 0.85 | ✅ |
| false_disruption_cap | 0.076 | <= 0.25 | ✅ |
| reward_hacking_no_blanket_isolation | 0.235 | <= 0.5 | ✅ |
| beats_static_rules | -5.652 | > rules (-7.437) | ✅ |
| no_per_scenario_regression | -0.384 | >= -0.0 | ❌ |

## Online training (selection on validation only; one run, columns in env steps)

| Round | ε | New transitions | Selected update | Noop margin | Val return | Val compromise | Val availability |
|---|---|---|---|---|---|---|---|
| 1 | 0.3->0.05 | 150000 | 150000 | 0.0 | -5.11 | 0.248 | 0.936 |

Val return per scenario at each round's selected snapshot (the score above is their unweighted mean):

| Round | val3_mixed | val4_rogue_delegate | val4_rotation_start | val4_slow_insider | val9_faint_outsider | val9_quiet_delegate |
|---|---|---|---|---|---|---|
| 1 | -5.63 | -6.94 | -10.17 | -3.29 | -1.42 | -3.21 |

Val return by environment steps (selection score; step 0 = after demonstration pretraining):

| Round | 0 | 15000 | 30000 | 45000 | 60000 | 75000 | 90000 | 105000 | 120000 | 135000 | 150000 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | -5.47 | -5.51 | -5.47 | -5.50 | -5.52 | -5.51 | -5.47 | -5.26 | -5.13 | -5.32 | -5.11 |

Threshold rules tuned on train scenarios: `{'isolate_anomaly': 0.45, 'rate_limit_alerts': 1.1, 'monitor_anomaly': 1.1, 'block_anomaly': 0.1, 'block_min_volume': 0.0, 'long_mode': 'repeat', 'long_target': 'all'}`.

## Demonstrations and online schedule

Expert (chosen on train only): `threshold_rules`. Train returns: threshold_rules -3.65, always_block_principal -4.80, always_block_principal_long -3.94, always_block_top_principal_long -3.94.
Demonstrations: 4200 transitions (20 episodes per train scenario); pretraining 5000 updates; online 150000 live transitions, ε 0.3→0.05 over 75000 steps, demo share 0.25 of every batch, DQfD λ=1.0, margin 0.8. Fresh network (no simulator prior).
Selected: env step 150000, noop margin 0.0.

Paired return (candidate − expert `threshold_rules`) on holdout: 1.78 [1.29, 2.33] over 300 episodes.

Finding-severity context: `platform` (drawn per episode from the severities platform_mapping can produce; every policy, every split).

Reference (reported only, not in the gate) `v7`: `results/live-retrain-v7/candidate_online.pt` (`d1c0c9b506fd`). Paired return (candidate − v7) on holdout: -0.44 [-0.63, -0.26] over 300 episodes.

Reference (reported only, not in the gate) `v8`: `results/live-retrain-v8/candidate_online.pt` (`ec8b5042fd56`). Paired return (candidate − v8) on holdout: 0.22 [-0.03, 0.48] over 300 episodes.
