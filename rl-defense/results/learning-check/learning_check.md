# Learning check: trained vs untrained vs baselines

_Results are from a simulated environment and do not establish real-world effectiveness._

Commit `78c72e379950`, 3 training seeds [0, 1, 2], 150,000 steps each, held-out eval configs, episode seeds 1000-1099 (100 per config per seed). A short check, not the protocol-17 evaluation.

| Policy | Return [95% CI over seeds] | Compromise % | False disruption % | Uptime % |
|---|---|---|---|---|
| ddqn_trained | -47.4 [-55.0, -32.6] | 16.1 | 67.8 | 90.5 |
| ddqn_untrained | -229.6 [-293.7, -192.7] | 61.1 | 92.7 | 34.5 |
| random | -154.1 [-155.1, -152.9] | 8.9 | 94.4 | 41.2 |
| noop | -386.2 [-386.2, -386.2] | 100.0 | n/a | 100.0 |
| threshold_rules | -96.0 [-96.0, -96.0] | 83.0 | 28.7 | 93.3 |

## Paired return difference (same episodes)

| Comparison | Mean diff [95% CI over episodes] | Episodes | Verdict |
|---|---|---|---|
| ddqn_trained_minus_ddqn_untrained | +182.2 [+177.3, +187.2] | 900 | trained better |
| ddqn_trained_minus_random | +106.7 [+103.3, +110.1] | 900 | trained better |
| ddqn_trained_minus_noop | +338.8 [+331.1, +346.6] | 900 | trained better |
| ddqn_trained_minus_threshold_rules | +48.7 [+43.8, +53.4] | 900 | trained better |

## Did the parameters and the behaviour change?

| Seed | Gradient updates | Sum of abs weight change from init | Same greedy action as untrained |
|---|---|---|---|
| 0 | 149,000 | 3711.7 | 12.8% of states |
| 1 | 149,000 | 3507.3 | 4.9% of states |
| 2 | 149,000 | 3897.8 | 18.0% of states |
