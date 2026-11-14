# Evidence-policy study

_Results are from a simulated environment and do not establish real-world effectiveness._

Commit `8c4a67831eb2`. v1 reward with c_false_disrupt = 0.25. Training seeds [0, 1, 2, 3, 4], 1,000,000 steps. Every policy is scored on the same episodes; 'Return (arm reward)' is the v1 return. CIs are 95% bootstrap over training seeds.

Improves on the original DDQN (all three checks): **False** {'compromise_not_above_original': False, 'false_disruption_lower': True, 'benign_load_lower': True}. Beats the monitor_isolate rule on return: **False**; on compromise: **False**.

## Validation

| Policy | Return (v0 reward) | Return (arm reward) | Compromise % [CI] | db lost % | False disruption % | Benign load | Disruptive actions/ep | Uptime % | Invalid |
|---|---|---|---|---|---|---|---|---|---|
| ddqn_guided | -33.8 | -52.3 | 25.7 [18.3, 34.1] | 1.1 | 25.8 | 0.373 | 22.5 | 94.0 | 0 |
| ddqn_v0 | -26.9 | -60.6 | 4.8 [2.0, 7.3] | 0.7 | 73.8 | 0.677 | 37.5 | 95.0 | 0 |
| random | -152.6 | -324.3 | 5.9 [4.5, 6.8] | 0.0 | 95.1 | 3.434 | 103.8 | 41.1 | 0 |
| monitor_isolate | -32.9 | -51.3 | 22.0 [22.0, 22.0] | 0.7 | 5.1 | 0.369 | 13.1 | 92.5 | 0 |
| exposed_guard | -25.0 | -59.2 | 3.3 [3.3, 3.3] | 0.0 | 77.9 | 0.683 | 44.4 | 95.7 | 0 |
| threshold_rules | -84.7 | -102.8 | 72.0 [72.0, 72.0] | 0.0 | 22.0 | 0.361 | 53.6 | 93.5 | 0 |
| noop | -383.4 | -383.4 | 100.0 [100.0, 100.0] | 92.0 | n/a | 0.000 | 0.0 | 100.0 | 0 |

## Held-out

| Policy | Return (v0 reward) | Return (arm reward) | Compromise % [CI] | db lost % | False disruption % | Benign load | Disruptive actions/ep | Uptime % | Invalid |
|---|---|---|---|---|---|---|---|---|---|
| ddqn_guided | -42.9 | -65.9 | 32.3 [26.3, 38.5] | 2.3 | 34.5 | 0.462 | 27.7 | 92.7 | 0 |
| ddqn_v0 | -35.4 | -74.1 | 10.5 [6.1, 13.8] | 0.9 | 72.4 | 0.776 | 41.7 | 93.5 | 0 |
| random | -154.3 | -324.8 | 8.9 [7.7, 10.0] | 0.1 | 94.3 | 3.412 | 103.6 | 41.2 | 0 |
| monitor_isolate | -42.2 | -62.5 | 25.7 [25.7, 25.7] | 5.3 | 6.7 | 0.411 | 14.2 | 91.8 | 0 |
| exposed_guard | -34.0 | -70.1 | 11.3 [11.3, 11.3] | 1.3 | 74.8 | 0.725 | 45.5 | 94.0 | 0 |
| threshold_rules | -96.0 | -118.8 | 83.0 [83.0, 83.0] | 0.3 | 28.7 | 0.455 | 60.5 | 93.3 | 0 |
| noop | -386.2 | -386.2 | 100.0 [100.0, 100.0] | 93.3 | n/a | 0.000 | 0.0 | 100.0 | 0 |
