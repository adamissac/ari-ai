# Evaluation analysis

Run: `protocol-v0-1182773` — 6000 evaluation episodes, held-out configs only.
*Results are from a simulated environment and do not establish real-world effectiveness.*

## Where each policy loses reward

Mean per-episode total of each reward component (negative = cost).

| Policy | Return | invalid_action | action_cost | escalation_cost | disruption | adversary_progress | containment | impact | terminal |
|---|---|---|---|---|---|---|---|---|---|
| ddqn | -65.6 | 0.0 | -1.5 | -1.0 | -17.1 | -8.8 | 2.1 | -26.3 | -13.0 |
| threshold_rules | -96.0 | 0.0 | -2.0 | -1.5 | -27.4 | -17.3 | 4.7 | -52.1 | -0.5 |
| random | -154.3 | 0.0 | -3.1 | -1.5 | -141.6 | -3.4 | 1.3 | -5.7 | -0.2 |
| noop | -386.2 | 0.0 | 0.0 | 0.0 | 0.0 | -19.0 | 0.0 | -96.1 | -271.1 |

## Which nodes fall

Share of episodes in which each node reached impact.

| Policy | gateway | api | auth | payments | db |
|---|---|---|---|---|---|
| ddqn | 31.1% | 10.9% | 8.5% | 9.7% | 9.8% |
| threshold_rules | 65.0% | 66.0% | 4.7% | 4.0% | 0.3% |
| random | 4.8% | 4.3% | 0.3% | 0.1% | 0.1% |
| noop | 87.3% | 93.3% | 75.3% | 73.0% | 93.3% |

## Action mix

Share of all steps.

| Policy | escalate_to_human | isolate | noop | raise_monitoring | rate_limit | request_reassessment |
|---|---|---|---|---|---|---|
| ddqn | 1.1% | 5.3% | 61.6% | 16.7% | 13.6% | 1.8% |
| threshold_rules | 1.5% | 3.2% | 49.8% | 18.4% | 27.1% | 0.0% |
| random | 1.5% | 33.4% | 21.9% | 22.6% | 18.4% | 2.2% |
| noop | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% | 0.0% |

## DDQN by training seed

Seed-to-seed variation (pooled over configs).

| Seed | Return | Compromise | False disruption | Uptime |
|---|---|---|---|---|
| 0 | -76.4 | 48.3% | 59.2% | 94.1% |
| 1 | -54.9 | 25.0% | 70.3% | 94.3% |
| 2 | -70.4 | 63.0% | 45.2% | 93.2% |
| 3 | -63.4 | 60.0% | 43.6% | 93.7% |
| 4 | -62.8 | 41.3% | 51.3% | 93.7% |

## Failure cases: the 3 worst DDQN episodes

### 1. `eval_aggressive_noisy`, training seed 4, episode seed 1054

- Return -462.9; episode length 43; nodes that reached impact: api, db, payments.
- First foothold at step 0; first impact at step 6.
- Defender took 24 non-noop actions; first ten: raise_monitoring:auth, raise_monitoring:auth, raise_monitoring:payments, raise_monitoring:payments, rate_limit:api, rate_limit:gateway, request_reassessment:auth, isolate:auth, rate_limit:api, raise_monitoring:api.
- Largest costs: terminal -396.8, impact -45.6, adversary_progress -17.0.
- Replay: `failure_cases/ddqn_seed4_eval_aggressive_noisy_ep1054.json` (deterministic; matches the recorded return).

### 2. `eval_aggressive_noisy`, training seed 4, episode seed 1042

- Return -439.7; episode length 63; nodes that reached impact: api, db, payments.
- First foothold at step 1; first impact at step 6.
- Defender took 31 non-noop actions; first ten: raise_monitoring:auth, raise_monitoring:auth, raise_monitoring:payments, rate_limit:api, raise_monitoring:payments, rate_limit:gateway, raise_monitoring:api, request_reassessment:auth, isolate:auth, rate_limit:api.
- Largest costs: terminal -348.8, impact -69.1, adversary_progress -17.2.
- Replay: `failure_cases/ddqn_seed4_eval_aggressive_noisy_ep1042.json` (deterministic; matches the recorded return).

### 3. `eval_aggressive_noisy`, training seed 0, episode seed 1054

- Return -437.8; episode length 152; nodes that reached impact: api, auth, db, payments.
- First foothold at step 0; first impact at step 18.
- Defender took 89 non-noop actions; first ten: request_reassessment:api, request_reassessment:payments, rate_limit:api, escalate_to_human, raise_monitoring:api, raise_monitoring:api, request_reassessment:gateway, rate_limit:payments, rate_limit:gateway, isolate:gateway.
- Largest costs: impact -208.1, terminal -168.8, disruption -33.9.
- Replay: `failure_cases/ddqn_seed0_eval_aggressive_noisy_ep1054.json` (deterministic; matches the recorded return).

