Env: DefenseSimEnv-v0, eval configs: eval_aggressive_noisy (0f088b0baba76eef), eval_shifted_severity (8408d6aa4d5bdf4d), eval_stealthy_lowsignal (b712960bd39563c8)
Training seeds: [0, 1, 2, 3, 4] × 100 episodes per config (eval seeds 1000–1099); 200000 training steps per seed; git 118277336a2c

Pooled over held-out configs. Mean [95% bootstrap CI across training seeds].

| Policy | Return | Compromise % | TTC (steps) | False disruption % | Escalations | Uptime % | Invalid actions |
|---|---|---|---|---|---|---|---|
| ddqn | -65.6 [-72.1, -59.7] | 47.5 [35.3, 58.9] | 84.5 [65.1, 108.2] | 53.9 [45.8, 63.1] | 2.0 [1.3, 2.8] | 93.8 [93.5, 94.1] | 0.0 [0.0, 0.0] |
| random | -154.3 [-155.1, -153.4] | 8.9 [7.7, 10.0] | 23.2 [21.4, 24.8] | 94.3 [94.1, 94.5] | 3.0 [3.0, 3.0] | 41.2 [41.1, 41.3] | 0.0 [0.0, 0.0] |
| noop | -386.2 [-386.2, -386.2] | 100.0 [100.0, 100.0] | 190.3 [190.3, 190.3] | n/a | 0.0 [0.0, 0.0] | 100.0 [100.0, 100.0] | 0.0 [0.0, 0.0] |
| threshold_rules | -96.0 [-96.0, -96.0] | 83.0 [83.0, 83.0] | 158.3 [158.3, 158.3] | 28.7 [28.7, 28.7] | 3.0 [3.0, 3.0] | 93.3 [93.3, 93.3] | 0.0 [0.0, 0.0] |

Per held-out config (return / compromise %):

| Policy | eval_aggressive_noisy | eval_shifted_severity | eval_stealthy_lowsignal |
|---|---|---|---|
| ddqn | -71.0 [-81.6, -61.3] / 37.2 [25.8, 52.4] | -50.3 [-69.5, -34.1] / 42.8 [23.2, 64.4] | -75.6 [-85.4, -64.2] / 62.6 [49.0, 76.2] |
| random | -160.9 [-162.5, -159.5] / 18.4 [16.6, 20.2] | -150.8 [-151.8, -150.3] / 5.0 [3.6, 7.2] | -151.0 [-151.9, -150.0] / 3.2 [1.6, 5.0] |
| noop | -484.5 [-484.5, -484.5] / 100.0 [100.0, 100.0] | -349.5 [-349.5, -349.5] / 100.0 [100.0, 100.0] | -324.6 [-324.6, -324.6] / 100.0 [100.0, 100.0] |
| threshold_rules | -133.2 [-133.2, -133.2] / 96.0 [96.0, 96.0] | -73.7 [-73.7, -73.7] / 84.0 [84.0, 84.0] | -81.3 [-81.3, -81.3] / 69.0 [69.0, 69.0] |

DDQN vs baselines (Welch t-test over training seeds, Holm-corrected):

| Comparison | Metric | Mean diff (ddqn − baseline) | Cohen's d | p | Verdict |
|---|---|---|---|---|---|
| ddqn_vs_random | return | 88.664 | 15.25 | 1.3e-05 | ddqn better |
| ddqn_vs_random | compromise_rate | 0.387 | 3.55 | 0.0047 | ddqn worse |
| ddqn_vs_random | time_to_containment | 61.327 | 3.04 | 0.00836 | ddqn worse |
| ddqn_vs_random | false_disruption_rate | -0.404 | -5.18 | 0.0012 | ddqn better |
| ddqn_vs_random | escalations | -0.952 | -1.39 | 0.0928 | no significant difference |
| ddqn_vs_random | action_cost | -2.112 | -6.10 | 0.000645 | ddqn better |
| ddqn_vs_random | service_uptime | 0.526 | 164.17 | 1.87e-11 | ddqn better |
| ddqn_vs_noop | return | 320.599 | 55.63 | 1e-07 | ddqn better |
| ddqn_vs_noop | compromise_rate | -0.525 | -4.84 | 0.00157 | ddqn better |
| ddqn_vs_noop | time_to_containment | -105.831 | -5.26 | 0.00114 | ddqn better |
| ddqn_vs_noop | false_disruption_rate | n/a | n/a | n/a | undefined (metric n/a for one policy) |
| ddqn_vs_noop | escalations | 2.048 | 2.99 | 0.0091 | ddqn worse |
| ddqn_vs_noop | action_cost | 2.511 | 7.25 | 0.00033 | ddqn worse |
| ddqn_vs_noop | service_uptime | -0.062 | -20.47 | 5.44e-06 | ddqn worse |
| ddqn_vs_threshold_rules | return | 30.457 | 5.28 | 0.00112 | ddqn better |
| ddqn_vs_threshold_rules | compromise_rate | -0.355 | -3.27 | 0.00666 | ddqn better |
| ddqn_vs_threshold_rules | time_to_containment | -73.795 | -3.67 | 0.0044 | ddqn better |
| ddqn_vs_threshold_rules | false_disruption_rate | 0.253 | 3.25 | 0.00682 | ddqn worse |
| ddqn_vs_threshold_rules | escalations | -0.912 | -1.33 | 0.103 | no significant difference |
| ddqn_vs_threshold_rules | action_cost | -0.975 | -2.82 | 0.0112 | ddqn better |
| ddqn_vs_threshold_rules | service_uptime | 0.005 | 1.55 | 0.0704 | no significant difference |

*Results are from a simulated environment and do not establish real-world effectiveness.*
