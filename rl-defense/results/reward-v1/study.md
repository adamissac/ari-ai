# Reward-v1 study

_Results are from a simulated environment and do not establish real-world effectiveness._

Commit `305523c1f477`. Training seeds [0, 1, 2, 3, 4], 300,000 steps each, in-training checkpoint selection. CIs are 95% bootstrap over training seeds. Benign load is the mean number of healthy nodes under a control per step (isolation 1.0, rate-limit 0.3).

Selection rule (validation only): false disruption <= 40% and benign load <= 0.3405 (half the c=0 arm); lowest compromise rate among those.
Selected `c_false_disrupt`: **0.5**.

## Validation

### c_false_disrupt = 0

| Policy | Return (v0 reward) | Return (arm reward) | Compromise % [CI] | db lost % | False disruption % | Benign load | Disruptive actions/ep | Uptime % | Invalid |
|---|---|---|---|---|---|---|---|---|---|
| ddqn | -32.4 | -32.4 | 11.3 [6.5, 16.1] | 1.7 | 64.5 | 0.681 | 33.9 | 93.7 | 0 |
| exposed_guard | -25.0 | -25.0 | 3.3 [3.3, 3.3] | 0.0 | 77.9 | 0.683 | 44.4 | 95.7 | 0 |
| noop | -383.4 | -383.4 | 100.0 [100.0, 100.0] | 92.0 | n/a | 0.000 | 0.0 | 100.0 | 0 |
| threshold_rules | -84.7 | -84.7 | 72.0 [72.0, 72.0] | 0.0 | 22.0 | 0.361 | 53.6 | 93.5 | 0 |
| random | -152.6 | -152.6 | 5.9 [4.5, 6.8] | 0.0 | 95.1 | 3.434 | 103.8 | 41.1 | 0 |

### c_false_disrupt = 0.1

| Policy | Return (v0 reward) | Return (arm reward) | Compromise % [CI] | db lost % | False disruption % | Benign load | Disruptive actions/ep | Uptime % | Invalid |
|---|---|---|---|---|---|---|---|---|---|
| ddqn | -29.5 | -39.6 | 24.0 [10.4, 40.8] | 1.5 | 56.8 | 0.507 | 27.0 | 94.4 | 0 |
| exposed_guard | -25.0 | -38.7 | 3.3 [3.3, 3.3] | 0.0 | 77.9 | 0.683 | 44.4 | 95.7 | 0 |
| noop | -383.4 | -383.4 | 100.0 [100.0, 100.0] | 92.0 | n/a | 0.000 | 0.0 | 100.0 | 0 |
| threshold_rules | -84.7 | -92.0 | 72.0 [72.0, 72.0] | 0.0 | 22.0 | 0.361 | 53.6 | 93.5 | 0 |
| random | -152.6 | -221.3 | 5.9 [4.5, 6.8] | 0.0 | 95.1 | 3.434 | 103.8 | 41.1 | 0 |

### c_false_disrupt = 0.25

| Policy | Return (v0 reward) | Return (arm reward) | Compromise % [CI] | db lost % | False disruption % | Benign load | Disruptive actions/ep | Uptime % | Invalid |
|---|---|---|---|---|---|---|---|---|---|
| ddqn | -35.0 | -57.5 | 20.0 [11.7, 30.1] | 3.2 | 45.5 | 0.455 | 24.7 | 94.3 | 0 |
| exposed_guard | -25.0 | -59.2 | 3.3 [3.3, 3.3] | 0.0 | 77.9 | 0.683 | 44.4 | 95.7 | 0 |
| noop | -383.4 | -383.4 | 100.0 [100.0, 100.0] | 92.0 | n/a | 0.000 | 0.0 | 100.0 | 0 |
| threshold_rules | -84.7 | -102.8 | 72.0 [72.0, 72.0] | 0.0 | 22.0 | 0.361 | 53.6 | 93.5 | 0 |
| random | -152.6 | -324.3 | 5.9 [4.5, 6.8] | 0.0 | 95.1 | 3.434 | 103.8 | 41.1 | 0 |

### c_false_disrupt = 0.5 (selected)

| Policy | Return (v0 reward) | Return (arm reward) | Compromise % [CI] | db lost % | False disruption % | Benign load | Disruptive actions/ep | Uptime % | Invalid |
|---|---|---|---|---|---|---|---|---|---|
| ddqn | -47.1 | -77.7 | 66.4 [37.9, 87.1] | 2.4 | 38.1 | 0.310 | 29.8 | 96.1 | 0 |
| exposed_guard | -30.0 | -86.6 | 14.7 [14.7, 14.7] | 1.3 | 68.8 | 0.566 | 43.7 | 96.3 | 0 |
| noop | -383.4 | -383.4 | 100.0 [100.0, 100.0] | 92.0 | n/a | 0.000 | 0.0 | 100.0 | 0 |
| threshold_rules | -84.7 | -120.9 | 72.0 [72.0, 72.0] | 0.0 | 22.0 | 0.361 | 53.6 | 93.5 | 0 |
| random | -152.6 | -496.0 | 5.9 [4.5, 6.8] | 0.0 | 95.1 | 3.434 | 103.8 | 41.1 | 0 |

## Held-out

### c_false_disrupt = 0

| Policy | Return (v0 reward) | Return (arm reward) | Compromise % [CI] | db lost % | False disruption % | Benign load | Disruptive actions/ep | Uptime % | Invalid |
|---|---|---|---|---|---|---|---|---|---|
| ddqn | -46.2 | -46.2 | 16.3 [9.5, 22.4] | 3.1 | 72.2 | 0.912 | 42.3 | 91.5 | 0 |
| exposed_guard | -34.0 | -34.0 | 11.3 [11.3, 11.3] | 1.3 | 74.8 | 0.725 | 45.5 | 94.0 | 0 |
| noop | -386.2 | -386.2 | 100.0 [100.0, 100.0] | 93.3 | n/a | 0.000 | 0.0 | 100.0 | 0 |
| threshold_rules | -96.0 | -96.0 | 83.0 [83.0, 83.0] | 0.3 | 28.7 | 0.455 | 60.5 | 93.3 | 0 |
| random | -154.3 | -154.3 | 8.9 [7.7, 10.0] | 0.1 | 94.3 | 3.412 | 103.6 | 41.2 | 0 |

### c_false_disrupt = 0.1

| Policy | Return (v0 reward) | Return (arm reward) | Compromise % [CI] | db lost % | False disruption % | Benign load | Disruptive actions/ep | Uptime % | Invalid |
|---|---|---|---|---|---|---|---|---|---|
| ddqn | -39.4 | -52.5 | 30.3 [16.6, 42.6] | 3.2 | 60.9 | 0.664 | 30.7 | 92.6 | 0 |
| exposed_guard | -34.0 | -48.4 | 11.3 [11.3, 11.3] | 1.3 | 74.8 | 0.725 | 45.5 | 94.0 | 0 |
| noop | -386.2 | -386.2 | 100.0 [100.0, 100.0] | 93.3 | n/a | 0.000 | 0.0 | 100.0 | 0 |
| threshold_rules | -96.0 | -105.1 | 83.0 [83.0, 83.0] | 0.3 | 28.7 | 0.455 | 60.5 | 93.3 | 0 |
| random | -154.3 | -222.5 | 8.9 [7.7, 10.0] | 0.1 | 94.3 | 3.412 | 103.6 | 41.2 | 0 |

### c_false_disrupt = 0.25

| Policy | Return (v0 reward) | Return (arm reward) | Compromise % [CI] | db lost % | False disruption % | Benign load | Disruptive actions/ep | Uptime % | Invalid |
|---|---|---|---|---|---|---|---|---|---|
| ddqn | -45.0 | -70.7 | 28.1 [15.7, 40.8] | 5.1 | 48.5 | 0.522 | 29.2 | 93.6 | 0 |
| exposed_guard | -34.0 | -70.1 | 11.3 [11.3, 11.3] | 1.3 | 74.8 | 0.725 | 45.5 | 94.0 | 0 |
| noop | -386.2 | -386.2 | 100.0 [100.0, 100.0] | 93.3 | n/a | 0.000 | 0.0 | 100.0 | 0 |
| threshold_rules | -96.0 | -118.8 | 83.0 [83.0, 83.0] | 0.3 | 28.7 | 0.455 | 60.5 | 93.3 | 0 |
| random | -154.3 | -324.8 | 8.9 [7.7, 10.0] | 0.1 | 94.3 | 3.412 | 103.6 | 41.2 | 0 |

### c_false_disrupt = 0.5 (selected)

| Policy | Return (v0 reward) | Return (arm reward) | Compromise % [CI] | db lost % | False disruption % | Benign load | Disruptive actions/ep | Uptime % | Invalid |
|---|---|---|---|---|---|---|---|---|---|
| ddqn | -58.3 | -94.7 | 70.9 [45.1, 90.2] | 5.1 | 41.4 | 0.369 | 31.6 | 95.0 | 0 |
| exposed_guard | -49.8 | -104.3 | 27.7 [27.7, 27.7] | 6.3 | 64.7 | 0.552 | 43.8 | 95.3 | 0 |
| noop | -386.2 | -386.2 | 100.0 [100.0, 100.0] | 93.3 | n/a | 0.000 | 0.0 | 100.0 | 0 |
| threshold_rules | -96.0 | -141.5 | 83.0 [83.0, 83.0] | 0.3 | 28.7 | 0.455 | 60.5 | 93.3 | 0 |
| random | -154.3 | -495.3 | 8.9 [7.7, 10.0] | 0.1 | 94.3 | 3.412 | 103.6 | 41.2 | 0 |
