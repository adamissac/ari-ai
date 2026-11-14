# Evidence-policy study

_Results are from a simulated environment and do not establish real-world effectiveness._

Commit `2618663aa870`. v1 reward with c_false_disrupt = 0.25. Training seeds [0, 1, 2, 3, 4], 300,000 steps. Every policy is scored on the same episodes; 'Return (arm reward)' is the v1 return. CIs are 95% bootstrap over training seeds.

Improves on the original DDQN (all three checks): **False** {'compromise_not_above_original': False, 'false_disruption_lower': True, 'benign_load_lower': True}. Beats the monitor_isolate rule on return: **True**; on compromise: **True**.

## Validation

| Policy | Return (v0 reward) | Return (arm reward) | Compromise % [CI] | db lost % | False disruption % | Benign load | Disruptive actions/ep | Uptime % | Invalid |
|---|---|---|---|---|---|---|---|---|---|
| ddqn_guided | -26.6 | -50.9 | 16.5 [4.5, 29.2] | 0.5 | 51.0 | 0.487 | 27.3 | 94.9 | 0 |
| ddqn_unguided | -35.0 | -57.5 | 20.0 [11.7, 30.1] | 3.2 | 45.5 | 0.455 | 24.7 | 94.3 | 0 |
| ddqn_v0 | -32.4 | -66.2 | 11.3 [6.5, 16.1] | 1.7 | 64.5 | 0.681 | 33.9 | 93.7 | 0 |
| random | -152.6 | -324.3 | 5.9 [4.5, 6.8] | 0.0 | 95.1 | 3.434 | 103.8 | 41.1 | 0 |
| monitor_isolate | -32.9 | -51.3 | 22.0 [22.0, 22.0] | 0.7 | 5.1 | 0.369 | 13.1 | 92.5 | 0 |
| exposed_guard | -25.0 | -59.2 | 3.3 [3.3, 3.3] | 0.0 | 77.9 | 0.683 | 44.4 | 95.7 | 0 |
| threshold_rules | -84.7 | -102.8 | 72.0 [72.0, 72.0] | 0.0 | 22.0 | 0.361 | 53.6 | 93.5 | 0 |
| noop | -383.4 | -383.4 | 100.0 [100.0, 100.0] | 92.0 | n/a | 0.000 | 0.0 | 100.0 | 0 |

## Held-out

| Policy | Return (v0 reward) | Return (arm reward) | Compromise % [CI] | db lost % | False disruption % | Benign load | Disruptive actions/ep | Uptime % | Invalid |
|---|---|---|---|---|---|---|---|---|---|
| ddqn_guided | -33.4 | -61.0 | 22.6 [8.2, 39.3] | 1.9 | 52.6 | 0.555 | 29.6 | 94.0 | 0 |
| ddqn_unguided | -45.0 | -70.7 | 28.1 [15.7, 40.8] | 5.1 | 48.5 | 0.522 | 29.2 | 93.6 | 0 |
| ddqn_v0 | -46.2 | -91.4 | 16.3 [9.5, 22.4] | 3.1 | 72.2 | 0.912 | 42.3 | 91.5 | 0 |
| random | -154.3 | -324.8 | 8.9 [7.7, 10.0] | 0.1 | 94.3 | 3.412 | 103.6 | 41.2 | 0 |
| monitor_isolate | -42.2 | -62.5 | 25.7 [25.7, 25.7] | 5.3 | 6.7 | 0.411 | 14.2 | 91.8 | 0 |
| exposed_guard | -34.0 | -70.1 | 11.3 [11.3, 11.3] | 1.3 | 74.8 | 0.725 | 45.5 | 94.0 | 0 |
| threshold_rules | -96.0 | -118.8 | 83.0 [83.0, 83.0] | 0.3 | 28.7 | 0.455 | 60.5 | 93.3 | 0 |
| noop | -386.2 | -386.2 | 100.0 [100.0, 100.0] | 93.3 | n/a | 0.000 | 0.0 | 100.0 | 0 |
