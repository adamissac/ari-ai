# RL Live Defense Lab audit: running progress

Started 2026-11-13 by Claude (agent, for Alan). Updated with every merged change. Numbers
here are from commands that were actually run; anything not run says so.

## What the system is (verified in code)

- **Algorithm:** Double DQN (`rl-defense/rl_defense/agents/ddqn.py`): online and target
  MLPs, masked argmax, uniform replay, Huber loss, gradient clipping, hard or soft target
  sync, optional n-step returns, dueling head, CQL and DQfD terms for the offline live work.
- **Environment:** `DefenseSimEnv-v0` (`rl_defense/envs/defense_sim.py`), a Gymnasium
  simulator. Five nodes, a hidden adversary stage per node, 48 observable features,
  22 masked actions, episode ends at the horizon (truncation) or when the db node is lost
  (termination). It is partially observable: the policy sees noisy alerts, never the stage.
- **Training:** `rl_defense/train.py`; **evaluation:** `rl_defense/evaluate.py`
  (held-out configs, 5 seeds x 100 episodes, bootstrap CIs, Welch + Holm).
- **Inference:** `rl_defense/inference.py` `PolicyRunner`, sha256-pinned checkpoint,
  produces a typed `DefenseRecommendation`. Nothing in the package applies an action to a
  real system.
- **Backend:** `backend/backend/pipeline.py` (recommendation job) and
  `backend/backend/live_defense/policy.py` (frozen v6 checkpoint in shadow mode; abstains
  and lets deterministic rules stand when a serving assumption fails).
- **Frontend `/lab`:** replays committed evaluation bundles
  (`rl-defense/results/protocol-*/defense_lab.json`), schema-validated. It is a recording
  of real evaluation episodes, not a running simulation. There is no start, pause or reset
  of a backend simulation today.

## Findings and status

| # | Finding | Evidence | Status |
|---|---|---|---|
| 1 | Inference served a recommendation for NaN, infinite and out-of-range observations (NaN margin, or a confident action from features of 50.0), and accepted integer or float action masks | `recommend_from_observation` on the committed protocol-v1 checkpoint before the fix | Fixed: `validate_policy_input`, `MalformedPolicyInput`; `tests/test_inference_guard.py` |
| 2 | Checkpoint load checked `obs_dim` against the env but not `n_actions` | `rl_defense/checkpoint.py` | Fixed, tested |
| 3 | Training writes one checkpoint at the end; no periodic checkpoint and no resume | `rl_defense/train.py` | Open |
| 4 | No committed comparison of the trained policy against an untrained network | `rl_defense/evaluate.py` compares noop, random, rules only | Open |
| 5 | `/lab` is a recording but its header reads "Defender: Active" with a live indicator | `frontend/app/lab/page.tsx` | Open |
| 6 | No interactive simulation (start, step, reset) behind the lab | no backend route | Open |

## Merged PRs

None yet.

## Next action

Open findings in order: 4 (measured learning proof), 3 (resume), 6 then 5.
