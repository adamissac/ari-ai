# RL Live Defense Lab audit: running progress

Started 2026-11-13 by Claude (agent, for Alan). Updated with every merged change. Numbers
here are from commands that were actually run; anything not run says so.

## What the system is (verified in code)

- **Algorithm:** Double DQN (`rl-defense/rl_defense/agents/ddqn.py`): online and target
  MLPs, masked argmax, uniform replay, Huber loss, gradient clipping, hard or soft target
  sync, optional n-step returns, dueling head, CQL and DQfD terms for the offline live work.
  The target is `r + gamma^k * (1 - done) * Q_target(s', argmax_valid Q_online(s'))`.
- **Environment:** `DefenseSimEnv-v0` (`rl_defense/envs/defense_sim.py`), a Gymnasium
  simulator. Five nodes, a hidden adversary stage per node, 48 observable features,
  22 masked actions. An episode ends at the horizon (truncation) or when the db node is
  lost (termination). It is partially observable: the policy sees noisy alerts and its own
  controls, never the adversary stage. The reward may read ground truth; the observation
  does not (`tests/test_env.py` has the leakage test).
- **Training:** `rl_defense/train.py`. **Evaluation:** `rl_defense/evaluate.py` (held-out
  configs, 5 seeds x 100 episodes, bootstrap CIs, Welch + Holm).
- **Inference:** `rl_defense/inference.py` `PolicyRunner`, sha256-pinned checkpoint,
  produces a typed `DefenseRecommendation`. Nothing in the package applies an action to a
  real system.
- **Backend:** `backend/backend/pipeline.py` (recommendation job),
  `backend/backend/live_defense/policy.py` (frozen v6 checkpoint in shadow mode; abstains
  and lets deterministic rules stand when a serving assumption fails), and
  `backend/backend/api/lab.py` (simulated episode on request).
- **Frontend `/lab`:** a recorded replay of committed evaluation bundles, plus a panel
  that runs a new simulated episode on the backend and steps through each decision.

## Findings and status

| # | Finding | Status |
|---|---|---|
| 1 | Inference served a recommendation for NaN, infinite and out-of-range observations and accepted non-boolean action masks | Fixed, #929 |
| 2 | Checkpoint load checked `obs_dim` but not `n_actions` | Fixed, #929 |
| 3 | Training wrote one checkpoint at the end: no periodic state, no resume, and a non-finite loss did not stop the run | Fixed, #930 |
| 4 | No comparison of the trained policy with an untrained network | Fixed, #931: `rl_defense.learning_check` and committed results |
| 5 | `/lab` is a recording but its header read "Defender: Active" with a green indicator | Fixed in the lab UI PR: "Recorded · recommendation-only" |
| 6 | No simulation could be started from the lab; nothing showed a policy's observation, mask, Q-values or reward | Fixed: engine #931, backend route and UI panel in their own PRs |
| 7 | Simulator training bootstraps through the time limit while the live pipeline stores the time limit as terminal. Both have time in the observation, so the simulator's last-step target reads a state (`time_fraction = 1`) that is never trained as a start state | Open, documented. Not changed: protocol-v0/v1 evidence is reproducible bit for bit with the current behaviour |
| 8 | The lab-trained policy has a high false-disruption rate (67.8% in the learning check, 75% for protocol-v1) and is worse than random on compromise rate | Open. A property of the reward and action set, already disclosed in `rl-defense/README.md` |

## Measured learning (finding 4)

`python -m rl_defense.learning_check --steps 150000 --seeds 0 1 2 --out results/learning-check`,
held-out eval configs, episode seeds 1000-1099, 100 episodes per config per seed. Two
independent runs gave identical numbers. Simulation output only.

| Policy | Return [95% CI over seeds] | Compromise % | False disruption % | Uptime % |
|---|---|---|---|---|
| ddqn_trained | -47.4 [-55.0, -32.6] | 16.1 | 67.8 | 90.5 |
| ddqn_untrained | -229.6 [-293.7, -192.7] | 61.1 | 92.7 | 34.5 |
| random | -154.1 [-155.1, -152.9] | 8.9 | 94.4 | 41.2 |
| noop | -386.2 | 100.0 | n/a | 100.0 |
| threshold_rules | -96.0 | 83.0 | 28.7 | 93.3 |

Paired on the same 900 episodes: trained minus untrained +182.2 [+177.3, +187.2];
minus random +106.7; minus noop +338.8; minus rules +48.7. Each training seed made
149,000 gradient updates; the trained policy picks the same greedy action as the
untrained one on 4.9% to 18.0% of states.

## Merged PRs

| PR | What | Merge commit |
|---|---|---|
| [#929](https://github.com/adamissac/ari-ai/pull/929) | Inference refuses malformed observations and masks; checkpoint load checks n_actions | c811dbda |
| [#930](https://github.com/adamissac/ari-ai/pull/930) | Resumable training and a stop on non-finite loss | 5902db1a |

## In flight

- #931: lab episode engine and learning check (this PR).
- `feat/alan/rl-audit-lab-api`: backend route `/lab/simulation`. Opens after #931 merges.
- `feat/alan/rl-audit-lab-ui`: transport methods, `/lab` simulation panel, e2e. Opens after the route merges.

## Next action

Merge the three in-flight changes in order. Then decide finding 7 with the ablation
numbers, and finding 8 with the owner (it is a reward-design choice, not a bug).
