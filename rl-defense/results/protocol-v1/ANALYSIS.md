# Evaluation analysis

Run: `protocol-v1` — 6000 evaluation episodes, held-out configs only.
*Results are from a simulated environment and do not establish real-world effectiveness.*

## Where each policy loses reward

Mean per-episode total of each reward component (negative = cost).

| Policy | Return | invalid_action | action_cost | escalation_cost | disruption | adversary_progress | containment | impact | terminal |
|---|---|---|---|---|---|---|---|---|---|
| ddqn | -29.1 | 0.0 | -1.6 | -0.3 | -19.1 | -5.7 | 2.1 | -3.4 | -1.1 |
| threshold_rules | -96.0 | 0.0 | -2.0 | -1.5 | -27.4 | -17.3 | 4.7 | -52.1 | -0.5 |
| random | -154.3 | 0.0 | -3.1 | -1.5 | -141.6 | -3.4 | 1.3 | -5.7 | -0.2 |
| noop | -386.2 | 0.0 | 0.0 | 0.0 | 0.0 | -19.0 | 0.0 | -96.1 | -271.1 |

## Which nodes fall

Share of episodes in which each node reached impact.

| Policy | gateway | api | auth | payments | db |
|---|---|---|---|---|---|
| ddqn | 2.0% | 2.0% | 1.3% | 2.0% | 1.1% |
| threshold_rules | 65.0% | 66.0% | 4.7% | 4.0% | 0.3% |
| random | 4.8% | 4.3% | 0.3% | 0.1% | 0.1% |
| noop | 87.3% | 93.3% | 75.3% | 73.0% | 93.3% |

## Action mix

Share of all steps.

| Policy | escalate_to_human | isolate | noop | raise_monitoring | rate_limit | request_reassessment |
|---|---|---|---|---|---|---|
| ddqn | 0.3% | 5.3% | 59.6% | 18.9% | 14.5% | 1.4% |
| threshold_rules | 1.5% | 3.2% | 49.8% | 18.4% | 27.1% | 0.0% |
| random | 1.5% | 33.4% | 21.9% | 22.6% | 18.4% | 2.2% |
| noop | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% | 0.0% |

## DDQN by training seed

Seed-to-seed variation (pooled over configs).

| Seed | Return | Compromise | False disruption | Uptime |
|---|---|---|---|---|
| 0 | -35.0 | 14.7% | 65.7% | 94.5% |
| 1 | -29.9 | 8.3% | 71.7% | 93.8% |
| 2 | -29.8 | 4.7% | 82.1% | 92.7% |
| 3 | -25.0 | 3.7% | 79.3% | 95.6% |
| 4 | -25.8 | 4.3% | 76.4% | 95.6% |

## Failure cases: the 3 worst DDQN episodes

### 1. `eval_stealthy_lowsignal`, training seed 0, episode seed 1089

- Return -305.5; episode length 78; nodes that reached impact: db, payments.
- First foothold at step 6; first impact at step 42.
- Defender took 31 non-noop actions; first ten: raise_monitoring:payments, rate_limit:gateway, request_reassessment:api, raise_monitoring:auth, raise_monitoring:auth, rate_limit:gateway, raise_monitoring:db, rate_limit:api, rate_limit:gateway, raise_monitoring:db.
- Largest costs: terminal -251.8, impact -33.4, adversary_progress -14.4.
- Replay: `failure_cases/ddqn_seed0_eval_stealthy_lowsignal_ep1089.json` (deterministic; matches the recorded return).

### 2. `eval_stealthy_lowsignal`, training seed 0, episode seed 1047

- Return -296.1; episode length 127; nodes that reached impact: api, db, payments.
- First foothold at step 0; first impact at step 5.
- Defender took 52 non-noop actions; first ten: rate_limit:gateway, raise_monitoring:payments, request_reassessment:api, raise_monitoring:auth, raise_monitoring:auth, isolate:api, rate_limit:gateway, isolate:api, raise_monitoring:db, rate_limit:gateway.
- Largest costs: terminal -195.2, impact -75.5, adversary_progress -14.4.
- Replay: `failure_cases/ddqn_seed0_eval_stealthy_lowsignal_ep1047.json` (deterministic; matches the recorded return).

### 3. `eval_stealthy_lowsignal`, training seed 2, episode seed 1081

- Return -229.7; episode length 109; nodes that reached impact: db, payments.
- First foothold at step 3; first impact at step 99.
- Defender took 45 non-noop actions; first ten: rate_limit:api, raise_monitoring:api, raise_monitoring:db, raise_monitoring:db, raise_monitoring:api, raise_monitoring:gateway, request_reassessment:payments, raise_monitoring:gateway, raise_monitoring:payments, rate_limit:api.
- Largest costs: terminal -192.9, adversary_progress -17.0, disruption -10.7.
- Replay: `failure_cases/ddqn_seed2_eval_stealthy_lowsignal_ep1081.json` (deterministic; matches the recorded return).

