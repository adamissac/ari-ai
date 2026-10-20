# Live retraining — held-out evaluation and promotion verdict

> Measured against the owned demo app (examples/payments-lite) in an isolated, in-process lab. Lab evidence only; not proof of real-world effectiveness (RQ-005).

**Decision: `reject`** (requires human approval: True).
Action space: `live_v3`; holdout scenarios from `configs/live/holdout_v7`.
Loop overrides: `{'c_disrupt': 1.0, 'delegation_aware_detector': True, 'finding_severity_context': 'platform'}`; val selection: `scenario_mean` over val3_mixed, val4_rogue_delegate, val4_rotation_start, val4_slow_insider.
Deployed `426b187b4244` (sim-trained) vs candidate `d1c0c9b506fd` (round 1, 48000 live transitions). Holdout: bookkeeper_and_outsider, quiet_week, steady_trickle × 30 episodes, paired.

## Held-out results (all scenarios)

| Policy | Return [95% CI] | Compromise | Availability | False disruption | No-attack duty | Actions/step |
|---|---|---|---|---|---|---|
| deployed | -15.26 [-17.77, -12.91] | 1.000 | 0.992 | 0.007 | 0.024 | 0.70 |
| candidate | -5.38 [-6.10, -4.62] | 0.122 | 0.882 | 0.107 | 0.382 | 0.11 |
| threshold_rules | -11.11 [-13.05, -9.38] | 0.472 | 0.923 | 0.073 | 0.264 | 0.06 |
| noop | -14.40 [-16.92, -12.04] | 1.000 | 1.000 | 0.000 | 0.000 | 0.00 |
| always_isolate_payments | -21.46 [-22.28, -20.66] | 0.000 | 0.364 | 0.671 | 1.000 | 0.33 |
| always_block_principal | -4.49 [-5.10, -3.88] | 0.154 | 0.913 | 0.053 | 0.184 | 0.18 |
| always_block_principal_long | -5.44 [-6.15, -4.72] | 0.092 | 0.870 | 0.126 | 0.444 | 0.10 |
| always_block_top_principal_long | -5.57 [-6.34, -4.80] | 0.152 | 0.880 | 0.117 | 0.409 | 0.12 |
| reference | -5.55 [-6.27, -4.83] | 0.166 | 0.897 | 0.086 | 0.306 | 0.64 |

Paired return gain (candidate − deployed): 9.88 [7.24, 12.62] over 90 episodes.

## Per held-out scenario (return / compromise / availability)

| Scenario | deployed | candidate | threshold_rules | noop | always_isolate_payments | always_block_principal | always_block_principal_long | always_block_top_principal_long | reference |
|---|---|---|---|---|---|---|---|---|---|
| bookkeeper_and_outsider | -11.74 / 1.00 / 0.99 | -9.27 / 0.20 / 0.76 | -9.01 / 0.16 / 0.76 | -10.87 / 1.00 / 1.00 | -19.11 / 0.00 / 0.37 | -7.73 / 0.27 / 0.84 | -9.17 / 0.15 / 0.75 | -9.56 / 0.29 / 0.79 | -9.24 / 0.30 / 0.82 |
| quiet_week | -3.15 / 1.00 / 0.99 | -3.62 / 0.49 / 0.94 | -2.54 / 0.94 / 0.99 | -2.33 / 1.00 / 1.00 | -26.71 / 0.00 / 0.31 | -2.74 / 0.56 / 0.96 | -4.25 / 0.43 / 0.92 | -4.25 / 0.43 / 0.92 | -4.12 / 0.49 / 0.94 |
| steady_trickle | -30.88 / 1.00 / 0.99 | -3.26 / 0.01 / 0.91 | -21.78 / 0.70 / 0.97 | -30.00 / 1.00 / 1.00 | -18.57 / 0.00 / 0.42 | -3.00 / 0.00 / 0.91 | -2.90 / 0.00 / 0.91 | -2.90 / 0.00 / 0.91 | -3.30 / 0.00 / 0.91 |

## Acceptance criteria (pre-registered in configs/live/promotion.yaml)

| Check | Value | Threshold | Pass |
|---|---|---|---|
| paired_reward_gain_ci_low | 7.235 | > 0.0 | ✅ |
| compromise_rate_not_worse | 0.122 | <= 1.0 x deployed (1.000) | ✅ |
| availability_floor | 0.882 | >= 0.85 | ✅ |
| false_disruption_cap | 0.107 | <= 0.25 | ✅ |
| reward_hacking_no_blanket_isolation | 0.382 | <= 0.5 | ✅ |
| beats_static_rules | -5.381 | > rules (-11.111) | ✅ |
| no_per_scenario_regression | -0.466 | >= -0.0 | ❌ |

## Online training (selection on validation only; one run, columns in env steps)

| Round | ε | New transitions | Selected update | Noop margin | Val return | Val compromise | Val availability |
|---|---|---|---|---|---|---|---|
| 1 | 0.3->0.05 | 45000 | 45000 | 0.2 | -7.02 | 0.291 | 0.917 |

Val return per scenario at each round's selected snapshot (the score above is their unweighted mean):

| Round | val3_mixed | val4_rogue_delegate | val4_rotation_start | val4_slow_insider |
|---|---|---|---|---|
| 1 | -8.04 | -6.95 | -9.97 | -3.10 |

Val return by environment steps (selection score; step 0 = after demonstration pretraining):

| Round | 0 | 15000 | 30000 | 45000 | 60000 | 75000 | 90000 | 105000 | 120000 | 135000 | 150000 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | -7.07 | -7.03 | -7.02 | -7.02 | -7.02 | -7.10 | -7.19 | -7.07 | -7.16 | -7.19 | -7.27 |

Threshold rules tuned on train scenarios: `{'isolate_anomaly': 0.45, 'rate_limit_alerts': 1.1, 'monitor_anomaly': 1.1, 'block_anomaly': 0.2, 'block_min_volume': 0.0, 'long_mode': 'repeat', 'long_target': 'all'}`.

## Demonstrations and online schedule

Expert (chosen on train only): `threshold_rules`. Train returns: threshold_rules -4.31, always_block_principal -6.09, always_block_principal_long -4.64, always_block_top_principal_long -4.64.
Demonstrations: 3000 transitions (20 episodes per train scenario); pretraining 5000 updates; online 45000 live transitions, ε 0.3→0.05 over 75000 steps, demo share 0.25 of every batch, DQfD λ=1.0, margin 0.8. Fresh network (no simulator prior).
Selected: env step 45000, noop margin 0.2.

Paired return (candidate − expert `threshold_rules`) on holdout: 5.73 [3.68, 7.76] over 90 episodes.

Finding-severity context: `platform` (drawn per episode from the severities platform_mapping can produce; every policy, every split).

Reference (reported only, not in the gate): `results/live-retrain-v6/candidate_online.pt` (`8113a37f4ff9`). Paired return (candidate − reference) on holdout: 0.17 [-0.14, 0.47] over 90 episodes.
