> **Artifact limitation (2026-10-19 review):** The original checkpoint and experience JSONL bytes were not committed or provided in a durable store. The recorded `recommend_promote` verdict and metrics below describe that historical run; they are not a currently executable promotion instruction or independently reloadable evidence. Its selected checkpoint was restored at step 105,000, but the old lineage counted all 150,000 online transitions (153,000 including demonstrations). Do not use that count as the selected checkpoint's training history. The old run also skipped the first 60 online updates. Future runs retain selected-prefix lineage, the complete experiment separately, and all hash-pinned artifact bytes. No historical bytes, hashes, metrics or corrected-run results have been fabricated.

# Live retraining — held-out evaluation and promotion verdict

> Measured against the owned demo app (examples/payments-lite) in an isolated, in-process lab. Lab evidence only; not proof of real-world effectiveness (RQ-005).

**Decision: `recommend_promote`** (requires human approval: True).
Action space: `live_v3`; holdout scenarios from `configs/live/holdout_v6`.
Loop overrides: `{'c_disrupt': 1.0, 'delegation_aware_detector': True}`; val selection: `scenario_mean` over val3_mixed, val4_rogue_delegate, val4_rotation_start, val4_slow_insider.
Deployed `cb990dd4dedf` (sim-trained) vs candidate `8113a37f4ff9` (round 1, 153000 live transitions). Holdout: customer_turned_attacker, rotating_outsider_busy_books, slow_pair × 30 episodes, paired.

## Held-out results (all scenarios)

| Policy | Return [95% CI] | Compromise | Availability | False disruption | No-attack duty | Actions/step |
|---|---|---|---|---|---|---|
| deployed | -14.81 [-16.11, -13.61] | 1.000 | 1.000 | 0.000 | 0.000 | 0.63 |
| candidate | -5.30 [-6.03, -4.58] | 0.185 | 0.952 | 0.051 | 0.314 | 0.14 |
| threshold_rules | -7.58 [-8.44, -6.72] | 0.374 | 0.963 | 0.038 | 0.236 | 0.11 |
| noop | -14.33 [-15.62, -13.16] | 1.000 | 1.000 | 0.000 | 0.000 | 0.00 |
| always_isolate_payments | -26.28 [-27.62, -24.92] | 0.000 | 0.312 | 0.685 | 1.000 | 0.33 |
| always_block_principal | -6.66 [-7.54, -5.88] | 0.307 | 0.964 | 0.031 | 0.189 | 0.23 |
| always_block_principal_long | -3.89 [-4.34, -3.41] | 0.101 | 0.945 | 0.056 | 0.347 | 0.13 |
| always_block_top_principal_long | -3.89 [-4.34, -3.41] | 0.101 | 0.945 | 0.056 | 0.347 | 0.13 |

Paired return gain (candidate − deployed): 9.51 [8.17, 10.79] over 90 episodes.

## Per held-out scenario (return / compromise / availability)

| Scenario | deployed | candidate | threshold_rules | noop | always_isolate_payments | always_block_principal | always_block_principal_long | always_block_top_principal_long |
|---|---|---|---|---|---|---|---|---|
| customer_turned_attacker | -11.23 / 1.00 / 1.00 | -6.32 / 0.15 / 0.87 | -7.16 / 0.33 / 0.90 | -10.73 / 1.00 / 1.00 | -24.84 / 0.00 / 0.31 | -6.91 / 0.35 / 0.91 | -6.07 / 0.11 / 0.86 | -6.07 / 0.11 / 0.86 |
| rotating_outsider_busy_books | -16.63 / 1.00 / 1.00 | -1.25 / 0.07 / 1.00 | -4.20 / 0.26 / 1.00 | -16.07 / 1.00 / 1.00 | -34.61 / 0.00 / 0.25 | -2.79 / 0.17 / 1.00 | -1.10 / 0.06 / 1.00 | -1.10 / 0.06 / 1.00 |
| slow_pair | -16.57 / 1.00 / 1.00 | -8.33 / 0.44 / 0.96 | -11.38 / 0.65 / 0.97 | -16.20 / 1.00 / 1.00 | -19.40 / 0.00 / 0.40 | -10.28 / 0.55 / 0.96 | -4.49 / 0.16 / 0.95 | -4.49 / 0.16 / 0.95 |

## Acceptance criteria (pre-registered in configs/live/promotion.yaml)

| Check | Value | Threshold | Pass |
|---|---|---|---|
| paired_reward_gain_ci_low | 8.172 | > 0.0 | ✅ |
| compromise_rate_not_worse | 0.185 | <= 1.0 x deployed (1.000) | ✅ |
| availability_floor | 0.952 | >= 0.85 | ✅ |
| false_disruption_cap | 0.051 | <= 0.25 | ✅ |
| reward_hacking_no_blanket_isolation | 0.314 | <= 0.5 | ✅ |
| beats_static_rules | -5.298 | > rules (-7.578) | ✅ |
| no_per_scenario_regression | 4.909 | >= -0.0 | ✅ |

## Online training (selection on validation only; one run, columns in env steps)

| Round | ε | New transitions | Selected update | Noop margin | Val return | Val compromise | Val availability |
|---|---|---|---|---|---|---|---|
| 1 | 0.3->0.05 | 150000 | 105000 | 0.1 | -6.98 | 0.287 | 0.916 |

Val return per scenario at each round's selected snapshot (the score above is their unweighted mean):

| Round | val3_mixed | val4_rogue_delegate | val4_rotation_start | val4_slow_insider |
|---|---|---|---|---|
| 1 | -8.04 | -6.81 | -9.97 | -3.10 |

Val return by environment steps (selection score; step 0 = after demonstration pretraining):

| Round | 0 | 15000 | 30000 | 45000 | 60000 | 75000 | 90000 | 105000 | 120000 | 135000 | 150000 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | -7.05 | -7.04 | -7.09 | -7.07 | -7.02 | -7.06 | -7.06 | -6.98 | -7.04 | -7.12 | -7.12 |

Threshold rules tuned on train scenarios: `{'isolate_anomaly': 0.45, 'rate_limit_alerts': 1.1, 'monitor_anomaly': 1.1, 'block_anomaly': 0.2, 'block_min_volume': 0.0, 'long_mode': 'repeat', 'long_target': 'all'}`.

## Demonstrations and online schedule

Expert (chosen on train only): `threshold_rules`. Train returns: threshold_rules -4.31, always_block_principal -6.09, always_block_principal_long -4.64, always_block_top_principal_long -4.64.
Demonstrations: 3000 transitions (20 episodes per train scenario); pretraining 5000 updates; online 150000 live transitions, ε 0.3→0.05 over 75000 steps, demo share 0.25 of every batch, DQfD λ=1.0, margin 0.8. Fresh network (no simulator prior).
Selected: env step 105000, noop margin 0.1.

Paired return (candidate − expert `threshold_rules`) on holdout: 2.28 [1.80, 2.76] over 90 episodes.
