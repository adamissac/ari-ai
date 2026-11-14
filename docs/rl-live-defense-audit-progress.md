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
| 5 | `/lab` is a recording but its header read "Defender: Active" with a green indicator | Fixed, #932: "Recorded · recommendation-only" |
| 6 | No simulation could be started from the lab; nothing showed a policy's observation, mask, Q-values or reward | Fixed: engine #931, backend route and UI panel #932 |
| 7 | Simulator training bootstraps through the time limit while the live pipeline stores the time limit as terminal. Both have time in the observation, so the simulator's last-step target reads a state (`time_fraction = 1`) that is never trained as a start state | Analysed, opt-in fix in #941 (`train(time_limit_terminal=True)`, `--time-limit-terminal`). Default unchanged; see "Finding 7" below |
| 8 | The lab-trained policy has a high false-disruption rate (67.8% in the learning check, 75% for protocol-v1) | Cause found and a versioned reward tested, #941. No better policy came out of it; see "Finding 8" below |
| 9 | Live promotion gate passed undefined metrics (`or 0.0`, `else 1.0`), skipped the rules check when no rules rows were given, and compared unpaired episode sets silently | Fixed, #941 |
| 10 | Registry `save()` was not atomic; `rollback` did not verify the target checkpoint bytes | Fixed, #941 |
| 11 | v6 shadow observation double-counted 401/403 (`auth_failures + status_4xx`), unlike the lab detector v6 trained on | Fixed, #941 |
| 12 | No test proved the v6 checkpoint produces a recommendation in the backend shadow path (existing tests accept either outcome) | Fixed, #941: `backend/tests/test_shadow_inference_v6.py`, in the `rl-integration` job |
| 13 | The tuned `threshold_rules` baseline is weak: a simple deterministic rule (`ExposedGuardPolicy`) reaches -34.0 return and 11.3% compromise held-out against -96.0 and 83% | Baseline added, #941 |

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
| [#931](https://github.com/adamissac/ari-ai/pull/931) | Lab episode engine and the learning check with results | 0d2a7baa |
| [#932](https://github.com/adamissac/ari-ai/pull/932) | Backend route `/lab/simulation`, transport methods, `/lab` simulation panel, e2e | b32b2130 |
| [#935](https://github.com/adamissac/ari-ai/pull/935) | Audit progress doc | 5cea8359 |
| [#941](https://github.com/adamissac/ari-ai/pull/941) | Fail-closed gate, registry hardening, v6 shadow fix and tests, opt-in v1 reward and study, opt-in time-limit option | see GitHub |
| [#941](https://github.com/adamissac/ari-ai/pull/941) merged | as above | d5a967bf |
| [#945](https://github.com/adamissac/ari-ai/pull/945) | Guided exploration, `monitor_isolate` rule, evidence-policy study | dd73a920 |
| [#939](https://github.com/adamissac/ari-ai/pull/939) | 8-seed truncation ablation, simulator fuzz | f952a72f |
| [#938](https://github.com/adamissac/ari-ai/pull/938) | Same-episode policy comparison in the lab panel; session handoff | 92a712d3 |

## Finding 7: measured, not changed

Ablation with the learning-check settings, storing the time limit as a terminal transition
during training only. 8 training seeds (0-7), 150k steps each, the same 300 held-out
episodes per seed for both variants. Scratch runs; raw output is not committed.

| Variant | Return [95% CI over seeds] | Compromise % | False disruption % | Uptime % |
|---|---|---|---|---|
| Current (bootstrap through the time limit) | -61.0 [-86.5, -44.7] | 26.9 | 59.9 | 91.2 |
| Time limit stored as terminal | -44.4 [-54.5, -35.8] | 21.5 | 63.4 | 92.2 |

Paired by seed, the difference in return is +16.7 [-1.9, +41.3]; 7 of 8 seeds are better
with the terminal variant; Wilcoxon p = 0.15. That is not a demonstrated difference. Most
of the gap is one seed of the current variant that ended at -145 (compromise 76%), against
-52 for the same seed in the other variant. The clearer result is seed variance: at 150k
steps without in-training checkpoint selection, the final weights of one seed in eight
were poor. protocol-v1 uses in-training selection for this reason. No default was changed;
doing so would break bit-for-bit reproduction of protocol-v0/v1.

## Simulator invariants

A fuzz over all six scenario configs (60 episodes each, 72,000 steps, 10% deliberately
invalid actions) found no violation of: observation inside the Box space; reward equal to
the sum of its components; an invalid action flagged, penalized and applied as a no-op; a
valid isolate, rate-limit, reassessment, monitoring raise or escalation visible in the next
observation; termination only on database impact; truncation only at the horizon; the mask
never offering a rate-limit or isolate on an isolated node; `noop` always valid.

## Finding 8: cause, experiment, result

Full report: [`rl-defense/results/reward-v1/REPORT.md`](../rl-defense/results/reward-v1/REPORT.md).

- **Cause.** On the pinned protocol-v1 checkpoint, 95% of benign disruptions are on the two
  internet-exposed nodes and 84% are rate-limits of gateway or api, at a median target anomaly
  of 0.036. The v0 reward prices a benign rate-limit of the gateway at 0.027 per step, so
  standing prevention is nearly free. It is reward-rational, not a training defect.
- **Change.** `DefenseSimEnv-v1` (opt-in, `c_false_disrupt`): a per-step cost for each
  healthy node under a control, not scaled by criticality. v0 configs, hashes and rewards are
  unchanged (`tests/test_reward_v1.py`).
- **Result** (5 seeds x 300k steps per arm, held-out, seeds 1000-1099):

| Policy | Return (v0) | Compromise % | False disruption % | Benign load | Uptime % |
|---|---|---|---|---|---|
| DDQN, v0 reward | -46.2 | 16.3 [9.5, 22.4] | 72.2 | 0.912 | 91.5 |
| DDQN, c = 0.1 | -39.4 | 30.3 [16.6, 42.6] | 60.9 | 0.664 | 92.6 |
| DDQN, c = 0.25 | -45.0 | 28.1 [15.7, 40.8] | 48.5 | 0.522 | 93.6 |
| DDQN, c = 0.5 | -58.3 | 70.9 [45.1, 90.2] | 41.4 | 0.369 | 95.0 |
| exposed_guard (rule) | -34.0 | 11.3 | 74.8 | 0.725 | 94.0 |
| threshold_rules | -96.0 | 83.0 | 28.7 | 0.455 | 93.3 |
| random | -154.3 | 8.9 | 94.3 | 3.412 | 41.2 |

- **Reading.** Charging for benign disruption lowers it and raises compromise. No arm is a
  better defender, and none is recommended. At this budget the DDQN does not beat the
  `exposed_guard` rule; the 1M-step protocol-v1 policy (-29.1, 7.1%) beats it by a small
  margin. Deterministic controls stay authoritative.

### Follow-up with the trade-off fixed (owner decision, c = 0.25)

[`rl-defense/results/evidence-policy/REPORT.md`](../rl-defense/results/evidence-policy/REPORT.md).
A deterministic evidence-driven rule (`MonitorIsolatePolicy`: monitor exposed nodes, isolate
only on an anomaly signal) and a DDQN whose early exploration follows that rule
(`train(guide=...)`). Held-out, 5 seeds x 300k steps:

| Policy | Return (v1) | Return (v0) | Compromise % | False disruption % | Benign load |
|---|---|---|---|---|---|
| DDQN guided, v1 reward | -61.0 | -33.4 | 22.6 [8.2, 39.3] | 52.6 | 0.555 |
| DDQN, v0 reward | -91.4 | -46.2 | 16.3 [9.5, 22.4] | 72.2 | 0.912 |
| monitor_isolate rule | -62.5 | -42.2 | 25.7 | 6.7 | 0.411 |
| exposed_guard rule | -70.1 | -34.0 | 11.3 | 74.8 | 0.725 |

The guided policy is better than the original on return, disruption, db loss and uptime, and
not shown equal on compromise (overlapping intervals, per-seed 4% to 53%), so the
pre-stated acceptance check fails. No learned policy dominates the rules. Nothing promoted.

**Settled at 1M steps** (5 seeds, same episodes): guided v1 policy 32.3% compromise
[26.3, 38.5] and 34.5% false disruption; original-objective policy 10.5% [6.1, 13.8] and
72.4%. The intervals no longer overlap. The trade-off is real: lowering disruption costs
security in this simulator, and each learned policy is matched on its own objective by a
deterministic rule (`monitor_isolate` -62.5 vs -65.9 on v1 return; `exposed_guard` -34.0 vs
-35.4 on v0 return). The protocol-v1 policy stays; finding 8 is closed as "explained, not
fixable by training in this environment".

The lab's simulation panel offers `exposed_guard` and `monitor_isolate` as policies, so the
same-episode comparison shows the rules next to the trained policy.

## Finding 7: analysis

The scored objective is the return over a fixed 200-step horizon and the observation carries
`time_fraction`, so this is a time-aware finite-horizon problem: the value after the last step
is 0 by definition (Pardo et al. 2018, the time-aware case). The default bootstraps from
`Q(s_H)`, and `s_H` (`time_fraction = 1`) never occurs as a transition's start state, so that
value is never trained. Storing the horizon as terminal is the correct target here, and it is
what the live pipeline already does. The measured effect is small and not significant
(8 seeds: +16.7 [-1.9, +41.3]), consistent with a bounded error discounted by gamma = 0.99.
`time_limit_terminal` is therefore available and tested (`tests/test_time_limit.py`) but off
by default, so protocol-v0/v1 still reproduce. A larger ablation was not run in this round.

## Live pipeline and shadow path: audited in the follow-up

Traced: gateway records -> `telemetry.build_facts` -> `observations.from_platform_facts` /
`mask_from_facts` -> `PolicyRunner` -> `LiveDefenseLoop.step` (enforced control, measured
outcome, reward from measured counts) -> `LiveTransition` -> `experience`/`online` ->
`retrain` -> `evaluate.promotion_decision` -> `registry`; and in the backend
`engine.process_shadow` -> `policy.decide_inference` -> `_run_v6`.

- The live path uses the learned network: the backend loads the sha256-pinned v6 checkpoint
  and its Q-values match an independent load of the same bytes (new test). It abstains, with
  a recorded reason and no action, on a missing, tampered or swapped checkpoint, on
  unverified ownership, off-topology routes, synthetic sources, stale or quiet windows.
  Shadow decisions are audited as `NOT_EXECUTED`.
- Nothing retrains or promotes on its own; promotion needs a passing report bound to the
  checkpoint and incumbent hashes plus a `usr_*` id (which the local CLI does not
  authenticate, as its docstring says).
- Known serving differences left as they are, all in the recommendation-only path:
  `time_fraction` is always 0 and escalations always full at serving; active controls are not
  passed (`defense=None`), so v6 is not told a block is already in force; `anomaly_score` is
  the max of the runtime score and the lab formula; finding severities are 0 (ADR-0017, the
  reason quiet windows abstain). `mask_from_facts` hardcodes the reassessment threshold at
  0.1 while the live loop lowers severity to 0.2, so a repeated reassessment stays valid.
- Not done: the v1-v10 retrain result bundles were not re-run; `gateway.py`,
  `adversary.py`, `study.py`, `report.py` and `rl_defense/research/` were not read in depth.

## Next action

1. Owner decision on finding 8: the trade-off is now measured; a different reward form or a
   constraint would be new work.
2. If finding 7 matters for a future protocol, enable `time_limit_terminal` there and say so
   in that protocol; do not change v0/v1.
3. Pass active controls and time context into the v6 shadow observation if shadow
   recommendations are ever to be compared with rules quantitatively.
