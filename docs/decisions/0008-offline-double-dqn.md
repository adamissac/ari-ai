# ADR-0008: Offline Double DQN in a Gymnasium simulator; recommendations only

| Field | Value |
|---|---|
| Status | Proposed |
| Date | 2026-10-16 |
| Deciders | UNASSIGNED (ratify in DOCS-002) |
| Related | [09](../09_RL_DEFENSE_SYSTEM.md), [17](../17_RL_EVALUATION_PROTOCOL.md), RL-001…RL-005 |

## Context
P3 includes an RL defense component. Acting on real systems with a learned policy is unsafe and unverifiable in a hackathon.

## Decision
Train a Double DQN agent (PyTorch) in a custom Gymnasium environment (`DefenseSimEnv-v0`) with abstract adversary stages. Evaluate per protocol 17 against random, noop and threshold-rule baselines. Use checkpoints only to produce labeled recommendations; no code path to real actions.

## Options considered
| Option | Pros | Cons |
|---|---|---|
| Offline DDQN, recommend only | Safe; discrete actions fit DQN family; reproducible | Simulator realism limits claims |
| PPO | Robust, handles larger action spaces | Less sample-efficient for small discrete; more tuning |
| Rules only | Explainable | No learning story |
| Online RL on live signals | Realistic | Unsafe; unreproducible |

## Consequences
- Claims limited to the simulator.
- Env changes require version bumps.

## Revisit when
Simulator validated against real telemetry (RQ-005), or action space grows beyond DQN suitability.
