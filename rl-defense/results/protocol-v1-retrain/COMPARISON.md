# protocol-v1-retrain vs protocol-v0 (held-out evaluation)

Candidate: `candidate`, selected on the validation protocol in [experiments/README.md](../../experiments/README.md) without using held-out configs or seeds. Both runs: training seeds [0, 1, 2, 3, 4], 100 episodes × 3 held-out configs, eval seeds 1000–1099. Mean [95% bootstrap CI across training seeds], pooled over held-out configs.

v0 git `38fb5305` → protocol-v1-retrain git `6116267b`.

| Metric | v0 DDQN | protocol-v1-retrain DDQN | threshold_rules | Better? |
|---|---|---|---|---|
| Return | -65.6 [-72.1, -59.7] | -29.1 [-32.1, -26.1] | -96.0 | yes |
| Compromise % | 47.5 [35.3, 58.9] | 7.1 [4.1, 11.2] | 83.0 | yes |
| False disruption % | 53.9 [45.8, 63.1] | 75.0 [69.6, 79.8] | 28.7 | no |
| Uptime % | 93.8 [93.5, 94.1] | 94.4 [93.5, 95.4] | 93.3 | yes |
| Time to containment | 84.5 [65.1, 108.2] | 25.6 [20.9, 32.6] | 158.3 | yes |
| Escalations / episode | 2.0 [1.3, 2.8] | 0.7 [0.2, 1.2] | 3.0 | yes |
| gateway impacted % | 31.1 [16.5, 45.7] | 2.0 [1.0, 3.1] | 65.0 | yes |
| api impacted % | 10.9 [7.5, 16.2] | 2.0 [0.4, 3.6] | 66.0 | yes |
| auth impacted % | 8.5 [6.7, 10.9] | 1.3 [0.7, 1.8] | 4.7 | yes |
| payments impacted % | 9.7 [7.9, 11.3] | 2.0 [0.5, 4.7] | 4.0 | yes |
| db lost % | 9.8 [7.1, 11.9] | 1.1 [0.3, 2.1] | 0.3 | yes |

Per held-out config (return):

| Config | v0 DDQN | protocol-v1-retrain DDQN |
|---|---|---|
| eval_aggressive_noisy | -71.0 [-81.6, -61.3] | -30.5 [-32.4, -28.7] |
| eval_shifted_severity | -50.3 [-69.5, -34.1] | -25.1 [-28.7, -21.6] |
| eval_stealthy_lowsignal | -75.6 [-85.4, -64.2] | -31.6 [-43.3, -24.8] |

protocol-v1-retrain vs baselines (from its own eval_summary, Holm-corrected):

- **ddqn_vs_random** — return: ddqn better, compromise_rate: no significant difference, time_to_containment: no significant difference, false_disruption_rate: ddqn better, escalations: ddqn better, action_cost: ddqn better, service_uptime: ddqn better
- **ddqn_vs_noop** — return: ddqn better, compromise_rate: ddqn better, time_to_containment: ddqn better, false_disruption_rate: undefined (metric n/a for one policy), escalations: no significant difference, action_cost: ddqn worse, service_uptime: ddqn worse
- **ddqn_vs_threshold_rules** — return: ddqn better, compromise_rate: ddqn better, time_to_containment: ddqn better, false_disruption_rate: ddqn worse, escalations: ddqn better, action_cost: ddqn better, service_uptime: no significant difference

Stress test (held-out configs × adversary factor, seeds 3000–3049):

| Factor | v0 return | protocol-v1-retrain return | rules return | v0 db lost % | protocol-v1-retrain db lost % | rules db lost % |
|---|---|---|---|---|---|---|
| ×0.5 | -25.1 | -21.0 | -46.8 | 0.4 | 0.0 | 0.0 |
| ×1 | -66.9 | -30.6 | -97.1 | 9.5 | 1.7 | 0.7 |
| ×1.5 | -128.8 | -45.4 | -155.0 | 26.7 | 3.3 | 2.7 |
| ×2 | -198.2 | -60.5 | -204.1 | 44.8 | 6.5 | 4.7 |
| ×2.5 | -257.8 | -85.4 | -246.7 | 61.3 | 11.6 | 10.0 |

*Results are from a simulated environment and do not establish real-world effectiveness.*
