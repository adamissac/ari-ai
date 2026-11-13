# Why the DDQN disrupts healthy nodes, and what charging for it does

_Simulation output only. Nothing here establishes real-world effectiveness._

## Diagnosis (pinned protocol-v1 checkpoint, seed 0, held-out configs, episode seeds 1000-1099)

| Measure | Value |
|---|---|
| Disruptive actions on a healthy node ("false disruption") | 65.7% |
| ... of those, on an internet-exposed node (gateway, api) | 95.4% |
| ... of those, a rate-limit of gateway or api | 84% (6,221 of 7,372) |
| ... of those, taken while no node was compromised | 70.3% |
| Median anomaly score of the target at a benign disruption | 0.036 |
| Median anomaly score of the target at a justified disruption | 0.211 |

The policy keeps the two exposed nodes rate-limited without an alert signal. That is what the
v0 reward pays for: a benign rate-limit costs `0.3 x criticality x c_disrupt` per step (0.027
for the gateway) and cuts the entry probability by 70%. It is prevention the reward makes
nearly free, not a training defect. Training-side levers (exploration weight, selection
penalty, deployment margin) were already tried in round 4 (`experiments/README.md`) and all
traded false disruption for db loss.

A ten-line deterministic rule that does the same thing on purpose (`ExposedGuardPolicy`: keep
exposed nodes rate-limited, isolate on anomaly) scores, held-out under the v0 reward, return
-34.0 and 11.3% compromise with its threshold tuned on the training configs. The tuned
`threshold_rules` baseline scores -96.0 and 83%. The existing rules baseline understated what
a rule can do.

## Experiment

`python -m rl_defense.reward_v1_study --out <dir>` at commit `305523c1`. Four arms of
`c_false_disrupt` (0 = v0 reward), 5 training seeds each, 300,000 steps, same DDQN settings
and in-training selection. Full tables: [`study.md`](study.md), [`study.json`](study.json).
Checkpoints are not committed; the manifests are.

Held-out, mean over 5 training seeds [95% bootstrap CI]:

| Policy | Return (v0 reward) | Compromise % | db lost % | False disruption % | Benign load | Uptime % |
|---|---|---|---|---|---|---|
| DDQN, v0 reward (c = 0) | -46.2 | 16.3 [9.5, 22.4] | 3.1 | 72.2 | 0.912 | 91.5 |
| DDQN, c = 0.1 | -39.4 | 30.3 [16.6, 42.6] | 3.2 | 60.9 | 0.664 | 92.6 |
| DDQN, c = 0.25 | -45.0 | 28.1 [15.7, 40.8] | 5.1 | 48.5 | 0.522 | 93.6 |
| DDQN, c = 0.5 | -58.3 | 70.9 [45.1, 90.2] | 5.1 | 41.4 | 0.369 | 95.0 |
| exposed_guard (deterministic) | -34.0 | 11.3 | 1.3 | 74.8 | 0.725 | 94.0 |
| threshold_rules (deterministic) | -96.0 | 83.0 | 0.3 | 28.7 | 0.455 | 93.3 |
| random | -154.3 | 8.9 [7.7, 10.0] | 0.1 | 94.3 | 3.412 | 41.2 |
| noop | -386.2 | 100.0 | 93.3 | n/a | 0.000 | 100.0 |

Reference, not the same budget: the committed protocol-v1 policy (1M steps, 5 seeds) is at
-29.1 return, 7.1% compromise, 75.0% false disruption.

## What this shows

- The reward term does what it was built to do: false disruption falls from 72% to 41% and
  the benign load from 0.91 to 0.37 healthy nodes under a control per step.
- It does not give a better defender. Compromise rises from 16% to 28-30% at c = 0.1-0.25 and
  to 71% at c = 0.5. In this simulator, standing throttling of exposed nodes is what keeps
  the adversary out; a policy that stops doing it has only noisy alerts to act on and does
  not contain as well.
- The validation rule written before the run selected c = 0.5 because it bounded false
  disruption and benign load but not compromise. That was a flaw in the rule. No arm is
  recommended as a replacement policy.
- At this budget the DDQN does not beat `exposed_guard` under the v0 reward on return or
  compromise. The 1M-step protocol-v1 policy is 4.9 points better on return and 4.2 points
  lower on compromise than the rule, with a seed CI on compromise of [4.1, 11.2] that
  includes values close to the rule's. RL's margin over a simple rule here is small.

## Limits

- 300k steps, not the protocol's 1M. Five seeds. One reward form; other forms (a cost per
  disruptive action without evidence, a budget) were not tried.
- The held-out numbers for all arms were looked at together, so they are a comparison, not a
  single pre-registered held-out evaluation of one candidate.
- `DefenseSimEnv-v1` shares v0's observation and action space, so a checkpoint's `env_id`
  stays `DefenseSimEnv-v0`; the reward version is in the manifest's training-config hashes.
