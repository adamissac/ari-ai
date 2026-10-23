Env: DefenseSimEnv-v0, eval configs: eval_aggressive_noisy (0f088b0baba76eef), eval_shifted_severity (8408d6aa4d5bdf4d), eval_stealthy_lowsignal (b712960bd39563c8)
Training seeds: [0, 1, 2, 3, 4] × 100 episodes per config (eval seeds 1000–1099); 1000000 training steps per seed; git 6116267b5df6

Pooled over held-out configs. Mean [95% bootstrap CI across training seeds].

| Policy | Return | Compromise % | TTC (steps) | False disruption % | Escalations | Uptime % | Invalid actions |
|---|---|---|---|---|---|---|---|
| ddqn | -29.1 [-32.1, -26.1] | 7.1 [4.1, 11.2] | 25.6 [20.9, 32.6] | 75.0 [69.6, 79.8] | 0.7 [0.2, 1.2] | 94.4 [93.5, 95.4] | 0.0 [0.0, 0.0] |
| random | -154.3 [-155.1, -153.4] | 8.9 [7.7, 10.0] | 23.2 [21.4, 24.8] | 94.3 [94.1, 94.5] | 3.0 [3.0, 3.0] | 41.2 [41.1, 41.3] | 0.0 [0.0, 0.0] |
| noop | -386.2 [-386.2, -386.2] | 100.0 [100.0, 100.0] | 190.3 [190.3, 190.3] | n/a | 0.0 [0.0, 0.0] | 100.0 [100.0, 100.0] | 0.0 [0.0, 0.0] |
| threshold_rules | -96.0 [-96.0, -96.0] | 83.0 [83.0, 83.0] | 158.3 [158.3, 158.3] | 28.7 [28.7, 28.7] | 3.0 [3.0, 3.0] | 93.3 [93.3, 93.3] | 0.0 [0.0, 0.0] |

Per held-out config (return / compromise %):

| Policy | eval_aggressive_noisy | eval_shifted_severity | eval_stealthy_lowsignal |
|---|---|---|---|
| ddqn | -30.5 [-32.4, -28.7] / 1.4 [0.2, 2.6] | -25.1 [-28.7, -21.6] / 4.4 [1.4, 8.4] | -31.6 [-43.3, -24.8] / 15.6 [6.4, 27.6] |
| random | -160.9 [-162.5, -159.5] / 18.4 [16.6, 20.2] | -150.8 [-151.8, -150.3] / 5.0 [3.6, 7.2] | -151.0 [-151.9, -150.0] / 3.2 [1.6, 5.0] |
| noop | -484.5 [-484.5, -484.5] / 100.0 [100.0, 100.0] | -349.5 [-349.5, -349.5] / 100.0 [100.0, 100.0] | -324.6 [-324.6, -324.6] / 100.0 [100.0, 100.0] |
| threshold_rules | -133.2 [-133.2, -133.2] / 96.0 [96.0, 96.0] | -73.7 [-73.7, -73.7] / 84.0 [84.0, 84.0] | -81.3 [-81.3, -81.3] / 69.0 [69.0, 69.0] |

DDQN vs baselines (Welch t-test over training seeds, Holm-corrected):

| Comparison | Metric | Mean diff (ddqn − baseline) | Cohen's d | p | Verdict |
|---|---|---|---|---|---|
| ddqn_vs_random | return | 125.154 | 42.70 | 4.74e-08 | ddqn better |
| ddqn_vs_random | compromise_rate | -0.017 | -0.51 | 0.458 | no significant difference |
| ddqn_vs_random | time_to_containment | 2.390 | 0.40 | 0.553 | no significant difference |
| ddqn_vs_random | false_disruption_rate | -0.193 | -4.20 | 0.00265 | ddqn better |
| ddqn_vs_random | escalations | -2.341 | -5.08 | 0.0013 | ddqn better |
| ddqn_vs_random | action_cost | -2.682 | -9.73 | 0.000104 | ddqn better |
| ddqn_vs_random | service_uptime | 0.533 | 60.21 | 4.88e-08 | ddqn better |
| ddqn_vs_noop | return | 357.089 | 126.22 | 3.78e-09 | ddqn better |
| ddqn_vs_noop | compromise_rate | -0.929 | -28.64 | 1.42e-06 | ddqn better |
| ddqn_vs_noop | time_to_containment | -164.768 | -28.91 | 1.37e-06 | ddqn better |
| ddqn_vs_noop | false_disruption_rate | n/a | n/a | n/a | undefined (metric n/a for one policy) |
| ddqn_vs_noop | escalations | 0.659 | 1.43 | 0.0863 | no significant difference |
| ddqn_vs_noop | action_cost | 1.942 | 7.05 | 0.000369 | ddqn worse |
| ddqn_vs_noop | service_uptime | -0.056 | -6.34 | 0.000558 | ddqn worse |
| ddqn_vs_threshold_rules | return | 66.947 | 23.66 | 3.05e-06 | ddqn better |
| ddqn_vs_threshold_rules | compromise_rate | -0.759 | -23.39 | 3.19e-06 | ddqn better |
| ddqn_vs_threshold_rules | time_to_containment | -132.731 | -23.29 | 3.25e-06 | ddqn better |
| ddqn_vs_threshold_rules | false_disruption_rate | 0.464 | 10.11 | 8.97e-05 | ddqn worse |
| ddqn_vs_threshold_rules | escalations | -2.301 | -5.00 | 0.00139 | ddqn better |
| ddqn_vs_threshold_rules | action_cost | -1.544 | -5.60 | 0.000896 | ddqn better |
| ddqn_vs_threshold_rules | service_uptime | 0.011 | 1.25 | 0.12 | no significant difference |

*Results are from a simulated environment and do not establish real-world effectiveness.*
