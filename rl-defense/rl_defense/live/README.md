# `rl_defense.live` — the live defense loop (vertical slice)

Closes the loop the simulator cannot: a **trained DQN observes real telemetry** from the
owned demo app, **executes a permitted defensive action** that really takes effect,
**measures the actual outcome**, and **records a reward + training transition**. This is
the first code path in the project from a real application to an observation, from a
recommendation to an enforced action, and from a measured outcome back to a reward.

## The loop

```
reset(): start payments-lite in-process behind the gateway, drive one warm-up window
step(action):
  1. apply the permitted action to the gateway's enforced controls
  2. drive one window of REAL benign + attack HTTP traffic through the gateway
  3. measure the real outcome (compromised cross-tenant reads; blocked benign requests)
  4. reward = f(measured counts)         # not from any hidden state
  5. build next observation from measured telemetry (-> from_platform_facts -> 48-dim obs)
  6. return a replay-buffer-shaped LiveTransition
```

| Module | Role |
|---|---|
| `gateway.py` | `DefensiveGateway` wraps the target ASGI app; enforces `isolate`/`rate_limit`/`raise_monitoring` for real; records every request's true outcome. |
| `telemetry.py` | Real request records → `PlatformFacts` (measured `alert_rate`, `anomaly_score`). |
| `adversary.py` | `TrafficDriver`: real benign traffic + a real cross-tenant attacker abusing the planted BOLA in `GET /payments/{id}`. |
| `loop.py` | `LiveDefenseLoop`: the episode harness; loads any checkpoint via the existing `PolicyRunner`. |
| `contracts.py` | `LiveTransition`, `StepOutcome`, `DefenseControls` (local realization of the PROPOSED shared experience schema). |
| `run.py` | CLI: train-or-load a policy, run N live episodes, write transitions + a summary. |

## Run it

```sh
cd rl-defense
PYTHONPATH=.:../shared:../standards:../examples/payments-lite/target \
  .venv/bin/python -m rl_defense.live.run --steps 30000 --episodes 3 --horizon 30 \
  --out results/live-slice/transitions.jsonl
```

Reference output of this exact command is in [`../results/live-slice/`](../results/live-slice/).

## What is real, and what is not

**Real:** the target app (a real FastAPI service, in-process over an ASGI transport — no
sockets), the BOLA it contains, every HTTP request/response, the enforcement of each
defensive action, the compromise/disruption counts, the reward, and the transitions.

**Honest limits (RQ-005):**
- The policy shipped today is trained on the **abstract simulator**; how it behaves on
  real telemetry is itself a research question. The reference run shows the sim-trained
  policy under-containing on real signals (it raises monitoring instead of isolating) —
  a sim-to-real gap the simulator alone could never surface. Containment itself works:
  `tests/test_live_loop.py::test_isolating_payments_really_contains_and_moves_reward`
  proves that taking `isolate:payments` drives measured compromise to zero and raises the
  reward, so the reward signal is correct; the policy simply has not learned to use it.
- The route→node topology is the hand-written `configs/topology/payments_lite.yaml`.
- Numbers are lab evidence, not proof of real-world effectiveness.

## Tests

```sh
.venv/bin/python -m pytest -q tests/test_live_gateway.py tests/test_live_loop.py
```

`test_live_gateway.py` proves each action's real effect and that telemetry is measured;
`test_live_loop.py` proves the full trained-DQN loop produces well-formed transitions,
never picks a masked action, really contains when it isolates, and that
`request_reassessment` really lowers the observed finding severity after its delay.

## Safety

Owned, isolated target only; in-process (no network egress); only the permitted defensive
actions are enforced; no path to any system outside the demo app. See docs/15.
