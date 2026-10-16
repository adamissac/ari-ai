# rl-defense/

> **What exists: nothing yet (Phase 0).** Specs: [docs/09](../docs/09_RL_DEFENSE_SYSTEM.md),
> [docs/17](../docs/17_RL_EVALUATION_PROTOCOL.md),
> [docs/architecture/rl-training-and-inference](../docs/architecture/rl-training-and-inference.md).

## Purpose
Pillar 3's learning component: a simulated defense environment, a Double DQN
agent, mandatory baselines, a protocol-compliant evaluation harness, and an
inference function that turns a checkpoint into labeled recommendations.

## Responsibilities
- `DefenseSimEnv-v0` (Gymnasium) with abstract adversary stages, versioned configs,
  separate train and held-out eval configs.
- Double DQN training (PyTorch), replay buffer, seeded and CPU-reproducible.
- Baselines: `random`, `noop`, `threshold_rules`.
- Evaluation per protocol 17 → `eval_summary.json` + Markdown table.
- `recommend(observation) -> DefenseRecommendation` with fixed caveat text.

**Must not:** act on real infrastructure, model real exploit techniques, report
numbers not produced by the evaluation scripts.

## Interfaces
| Interface | Consumers |
|---|---|
| `python -m rl_defense.train --config --seed` | developers, CI smoke |
| `python -m rl_defense.evaluate --run-dir` | developers, DEMO-003 |
| `rl_defense.inference.recommend(...)` | backend (RL-005) |
| `rl_defense.observations.from_platform_facts(...)` | backend; maps criticality/finding severity/signals |
| Artifacts: checkpoints + manifest in `RL_RUNS_DIR` (git-ignored) | backend `RLCheckpoint` records |

## Dependencies
Python 3.12, Gymnasium, PyTorch, NumPy, Pydantic (configs), `shared/` for
`DefenseRecommendation`. No dependency on other platform packages for
training (RL-001…004 can start independently).

## Planned layout
```
rl-defense/
  rl_defense/ envs/ agents/ baselines/ train.py evaluate.py inference.py observations.py
  configs/train/  configs/eval/
  tests/
  runs/            # git-ignored
```

## First tasks
RL-001 → RL-002, RL-003 → RL-004 → RL-005.

## Commands
None yet.
