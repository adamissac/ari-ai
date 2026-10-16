# 17 — RL evaluation protocol

Status: **specified**. Applies to every result reported from `rl-defense/`,
including demo slides. Environment and agent: [09](09_RL_DEFENSE_SYSTEM.md).

## Goals

Produce comparisons that are reproducible, statistically honest and scoped to
the simulator. A result that does not follow this protocol must not be presented
as a result.

## Fixed setup

| Item | Rule |
|---|---|
| Env | `DefenseSimEnv-v0`, exact version + config hash recorded |
| Train configs | `configs/train/*.yaml` |
| Held-out eval configs | `configs/eval/*.yaml` — never used for training or threshold tuning |
| Seeds | Training: 5 seeds (0–4). Evaluation: 100 episodes per (policy, eval config, seed) with eval seeds 1000–1099 |
| Budget | Fixed env-step budget per training run (default 200k), same for all seeds |
| Baselines | `random`, `noop`, `threshold_rules` (tuned on train configs only) |
| Hardware | Recorded; results must not depend on GPU (CPU-reproducible) |

## Metrics

| Metric | Definition |
|---|---|
| Mean episodic return | Mean of total reward per episode |
| Compromise rate | % episodes where any node reached `impact` |
| Time to containment | Steps from first foothold to all nodes ≤ `foothold` and stable for 10 steps (censored at horizon) |
| False disruption rate | Disruptive actions (isolate/rate-limit) on nodes with stage `none` ÷ all disruptive actions |
| Escalation rate | `escalate_to_human` actions per episode |
| Action cost | Mean total action-cost component |

## Statistics

- Report mean ± 95% confidence interval across **training seeds** (n = 5),
  where each seed's value is its mean over 100 eval episodes per config.
- Use bootstrap CIs (10k resamples) or Welch's t-test for pairwise comparisons;
  report effect sizes, not just p-values.
- With 5 seeds, claim "outperforms" only if CIs do not overlap or the paired
  test is significant at α = 0.05 after Holm correction across metrics.
- Report all metrics, including ones where DDQN loses.

## Required checks before training

1. `gymnasium.utils.env_checker.check_env` passes.
2. Determinism: same seed + same actions → identical trajectories.
3. Reward sanity: `noop` loses more under aggressive adversary configs than under
   passive ones; `isolate`-everything has high false disruption.
4. Leakage check: observation contains no direct adversary stage (only noisy signals).

## Reporting template

Each evaluation produces `rl-defense/runs/<run_id>/eval_summary.json` and a
Markdown table:

```
Env: DefenseSimEnv-v0 (config hash …), eval configs: […], seeds: 0–4 × 100 eps
| Policy | Return (95% CI) | Compromise % | TTC | False disruption % | Escalations |
```

plus: git SHA, hyperparameters, training curves (mean ± CI band), and the
sentence: *"Results are from a simulated environment and do not establish
real-world effectiveness."*

## Ablations (post-MVP)

Vanilla DQN vs Double DQN; with/without finding-severity features; reward
coefficient sensitivity; adversary aggressiveness generalization.

## Anti-patterns (not allowed)

Cherry-picking the best seed; evaluating on training configs only; changing the
reward after seeing eval results without bumping env version; reporting training
return as evaluation; omitting the rule-based baseline.
