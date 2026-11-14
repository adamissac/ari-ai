# Evidence-policy study: guided DDQN under the v1 reward

_Simulation output only. Nothing here establishes real-world effectiveness._

Trade-off fixed by the owner (Alan, 2026-11-13): `c_false_disrupt = 0.25`. Command:
`python -m rl_defense.evidence_policy_study --out <dir>` at commit `2618663a`. 5 training
seeds x 300,000 steps per arm, held-out configs, episode seeds 1000-1099, every policy on the
same episodes. Full tables: [`study.md`](study.md), [`study.json`](study.json). Checkpoints
are not committed.

Guided exploration: for the first 100,000 steps the behaviour action is the
`monitor_isolate` rule's 70% of the time and uniformly random otherwise. Targets, loss and
the saved greedy policy are ordinary Double DQN.

| Policy | Return (v1 reward) | Return (v0 reward) | Compromise % [95% CI] | db lost % | False disruption % | Benign load | Uptime % |
|---|---|---|---|---|---|---|---|
| DDQN guided, v1 reward | **-61.0** | **-33.4** | 22.6 [8.2, 39.3] | 1.9 | 52.6 | 0.555 | 94.0 |
| DDQN unguided, v1 reward | -70.7 | -45.0 | 28.1 [15.7, 40.8] | 5.1 | 48.5 | 0.522 | 93.6 |
| DDQN, v0 reward (original objective) | -91.4 | -46.2 | 16.3 [9.5, 22.4] | 3.1 | 72.2 | 0.912 | 91.5 |
| monitor_isolate (rule) | -62.5 | -42.2 | 25.7 | 5.3 | 6.7 | 0.411 | 91.8 |
| exposed_guard (rule) | -70.1 | -34.0 | 11.3 | 1.3 | 74.8 | 0.725 | 94.0 |
| threshold_rules | -118.8 | -96.0 | 83.0 | 0.3 | 28.7 | 0.455 | 93.3 |
| random | -324.8 | -154.3 | 8.9 | 0.1 | 94.3 | 3.412 | 41.2 |
| noop | -386.2 | -386.2 | 100.0 | 93.3 | n/a | 0.000 | 100.0 |

## Reading

- Against the original-objective DDQN at the same budget, the guided policy has a better
  return under both rewards, 20 points less false disruption, 39% less benign load, fewer db
  losses and higher uptime.
- It is **not shown** to be as good on compromise: 22.6% against 16.3%, with overlapping
  intervals and large seed variance (per seed 4%, 10%, 13%, 33%, 53%). The acceptance rule
  written before the run required compromise not above the original's, so the study's
  verdict is "does not improve on all three checks".
- Guidance helps: against the unguided run with the same reward and seeds, v1 return is 9.7
  points better and db loss falls from 5.1% to 1.9%.
- Against the rule it was guided by, the guided DDQN is slightly better on v1 return
  (-61.0 vs -62.5) and compromise (22.6 vs 25.7) and far worse on false disruption (52.6 vs
  6.7). The rule is the least disruptive policy that still defends. No learned policy
  dominates the deterministic rules; `exposed_guard` still has the lowest compromise.
- No policy is promoted. The lab keeps its pinned protocol-v1 checkpoint.

## Settled at the protocol budget (1M steps)

`python -m rl_defense.evidence_policy_study --out <dir> --steps 1000000 --arms ddqn_guided ddqn_v0`
at commit `8c4a6783`, 5 seeds, same held-out episodes. Tables: [`steps-1m/study.md`](steps-1m/study.md).

| Policy | Return (v1 reward) | Return (v0 reward) | Compromise % [95% CI] | db lost % | False disruption % | Benign load | Uptime % |
|---|---|---|---|---|---|---|---|
| DDQN guided, v1 reward | -65.9 | -42.9 | 32.3 [26.3, 38.5] | 2.3 | 34.5 | 0.462 | 92.7 |
| DDQN, v0 reward (original objective) | -74.1 | -35.4 | 10.5 [6.1, 13.8] | 0.9 | 72.4 | 0.776 | 93.5 |
| monitor_isolate (rule) | -62.5 | -42.2 | 25.7 | 5.3 | 6.7 | 0.411 | 91.8 |
| exposed_guard (rule) | -70.1 | -34.0 | 11.3 | 1.3 | 74.8 | 0.725 | 94.0 |

- The compromise question is answered: the guided v1 policy is worse, 32.3% against 10.5%,
  with intervals that do not overlap and little seed variance (22% to 43% against 2% to 15%).
  The 300k-step overlap was noise.
- The trade-off is a property of the simulator, not of the training method: with three times
  the steps the v1 policy moved further toward low disruption (34.5%) and further from low
  compromise. Each reward's policy is the best learned policy under its own reward and the
  worse one under the other.
- Each learned policy is matched by a rule on its own objective: `monitor_isolate` has the
  better v1 return (-62.5 vs -65.9) and `exposed_guard` is within 1.4 points on v0 return
  (-34.0 vs -35.4) with similar compromise. The DDQN adds no measurable benefit over a
  ten-line rule in this environment.
- Decision recorded: the protocol-v1 policy stays the lab policy; no v1-reward policy is
  recommended. If low disruption is the priority, the `monitor_isolate` rule is the
  recommended reference, not a learned policy.

## Limits

Five seeds per arm, one coefficient, one guide, one simulator. The unguided v1 arm was not
rerun at 1M steps.
