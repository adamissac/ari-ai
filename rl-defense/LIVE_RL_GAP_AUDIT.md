# Live RL Defense Lab — implementation audit (Phases 0–9) and the live-loop gap

Date: 2026-10-19 · Author: Alan (agent) · Branch: `feat/alan/live-rl-loop`

**Question answered:** what will it take to prove that a *trained DQN observes real
telemetry from our isolated test app, executes a permitted defensive action, measures
the actual outcome, and records a valid reward + training transition?*

The audit maps onto the roadmap's build phases ([MASTER_ROADMAP](../docs/planning/MASTER_ROADMAP.md)
uses Phases 0–6); the RL pillar is docs/09 + docs/17. Evidence is file paths and the
92-test RL suite (`.venv/bin/python -m pytest -q rl-defense/tests` → **92 passed**, run
2026-10-19 on this machine).

## Per-phase status (RL-relevant slice)

| Phase | Area | Status | Evidence |
|---|---|---|---|
| 0 | Repo & architecture | ✅ complete | docs/, ADR-0008, [rl-training-and-inference](../docs/architecture/rl-training-and-inference.md) |
| 1 | Foundations / contracts | ✅ for RL | `shared.rl` contracts; `rl_defense/contracts.py` re-exports them; `tests/test_shared_contract.py` |
| 2 | Understand & review | n/a to RL loop | — |
| 3 | Seven agents | ✅ pipeline exists; not an RL input | `security-agents/`; deferred per ADR-0014 / PR #313 |
| 4 (RL-001…005) | RL trained & evaluated | ✅ **in simulation only** | below |
| 5 | Integration & demo | ⚠️ partial | backend/UI not wired (`README.md` row: "❌ not integrated yet") |

### What is fully implemented and tested (simulation)
- **Environment** `DefenseSimEnv-v0` — `rl_defense/envs/defense_sim.py`; `tests/test_env.py` (passes `check_env`, seeded-determinism, hidden-state-leakage).
- **Double DQN** — `rl_defense/agents/ddqn.py`; `tests/test_ddqn.py` (target math).
- **Training + checkpoint/manifest** — `rl_defense/train.py`, `rl_defense/checkpoint.py` (sha256 pin, `weights_only` load); `tests/test_training_and_eval.py`.
- **Protocol-17 evaluation** — `rl_defense/evaluate.py`; `results/protocol-v1/COMPARISON.md` (real output, independently recomputed).
- **Inference → `DefenseRecommendation`** — `rl_defense/inference.py` (`PolicyRunner.recommend_from_observation`), `rl_defense/api.py`; `tests/test_explain.py`, `tests/test_platform_mapping.py`.
- **Telemetry/finding → observation mapping (typed)** — `rl_defense/observations.py` (`from_platform_facts`, `mask_from_facts`), `rl_defense/platform_mapping.py` (`facts_from_platform`).

### What is still simulated / mocked / missing (the live gap)
Every number comes from the simulator's **hidden adversary state**. Specifically:

1. **No real telemetry source.** `facts_from_platform` *accepts* `RouteSignal(alert_rate, anomaly_score)` but nothing measures those from a running app — callers (tests) supply them. No collector turns real HTTP/behavioral signals into `NodeSignals`.
2. **No action execution.** `inference.py` states plainly: *"There is intentionally no function here (or anywhere in this package) that applies a recommendation to a real system."* `rate_limit`/`isolate`/`raise_monitoring` have simulated effects inside `DefenseSimEnv.step` only.
3. **No live episode loop.** The only `step()` is the simulator's; there is no loop that observes a real app, acts on it, and re-observes.
4. **No reward from a measured outcome.** Reward is computed from `_Hidden` adversary stages (`defense_sim.py:158` `step`), not from anything observed in a real system.
5. **No transition recorded outside the sim.** Transitions exist only in the in-sim `ReplayBuffer`.
6. **No trained checkpoint committed.** `runs/` is git-ignored (`.gitignore:47`); a checkpoint must be trained to run anything.

### What prevents a complete end-to-end live RL run
All of 1–5 above. The policy, env, inference, and the typed facts→obs bridge exist and
are tested, but there is **no code path from a real application to an observation, from a
recommendation to an enforced action, or from a measured outcome back to a reward +
transition**. That closing loop is the single missing piece.

## Highest-priority missing implementation (chosen)
**A live defense loop that closes the cycle against the owned, isolated test app
(`examples/payments-lite`)** — real telemetry in, permitted action enforced, real outcome
measured, reward + transition recorded. This is the exact capability the objective names,
and it unblocks everything downstream (experience collection, offline retraining, and later
the gated Phase 10). It is built in `rl_defense/live/` on this branch as a vertical slice,
in preference to more design docs or UI. See `rl_defense/live/README.md`.

### Safety (unchanged boundaries)
The loop runs the owned demo app in-process over an ASGI transport (no sockets, localhost
semantics only), enforces only the permitted defensive actions, and treats every produced
number as simulation-adjacent lab evidence, not proof of real-world effectiveness
(RQ-005). It adds no authority and no path to any system outside the isolated app.
