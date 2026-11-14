# Pilot gate pre-registration (written and committed before any run on these scenarios)

Decided with Alan (RL owner, with Adam) on 2026-11-14. This is the evaluation for the
"RL-gated pilot" gate (`docs/LIVE_DEFENSE_RL_EVALUATION_PLAN.md`, categories A-J). It trains
nothing and promotes nothing. A pass makes the backend report "RL validated, pilot ready
for owner approval"; RL stays shadow-only and recommendation-only either way.

**Candidate.** The frozen v6 checkpoint as it is served in the backend shadow path:
`results/live-retrain-v6/candidate_online.pt`, sha256
`8113a37f4ff9360a9efed2e9f499c4b2ae36e97bfb78372436f97da106fc05f1`, greedy with its saved
noop margin (0.1). No retraining, no re-selection.

**Scenarios (frozen, unused).** `configs/live/pilot_gate/`: pilot_insider_three_victims
(seeds 41600-41629), pilot_outsider_trio_rotation (42100-42129), pilot_quiet_heavy_books
(42600-42629), pilot_always_on_customer (44100-44129). 30 episodes each. Names and seeds are
disjoint from every train, val and holdout directory (asserted by a test). The v4 loop that
v6 was trained and judged in: `c_disrupt=1.0`, grant-aware detector, action space live_v3,
fixed finding severities.

**Baselines, on the same episodes.** The rules tuned on `train_v3` for the v6 run
(`results/live-retrain-v6/rules_tuning.json`, `selected`, not re-tuned), `always_block_principal`,
`always_block_principal_long`, `always_block_top_principal_long`, and `noop`. In live defense
the deterministic rules are the authority, so the rules are the incumbent the candidate is
compared with.

**Thresholds (owner-approved; `configs/live/promotion.yaml` as committed before any v6
result, plus one floor for delegated access).** The candidate passes only if all hold, pooled
over the four scenarios unless stated:

1. paired 95% CI lower bound of (candidate - rules) episode return > 0;
2. compromise rate <= the rules' compromise rate;
3. availability (legitimate requests not blocked by the defense) >= 0.85;
4. delegated success (authorized cross-tenant reads that succeed) >= 0.85;
5. false disruption (legitimate requests blocked in attack-free windows) <= 0.25;
6. attack-free defense duty <= 0.5;
7. return > the rules' return;
8. on no scenario does the candidate's mean return trail the rules'.

An undefined metric fails its check. Pass-by-total-reward is not a rule: checks 2-6 and 8
are required whatever the return.

**Also reported, with no threshold:** per-scenario metrics for every policy; abstention
(share of windows without a flagged principal in which the candidate takes no action, and
share with one in which it acts); uncertainty (harm rate by tercile of the Q-margin between
the best and second-best valid action; Q-values are scores, not probabilities); intervention
cost (non-noop actions per step).

**One run:**

```sh
cd rl-defense
PYTHONPATH=.:../shared:../standards:../examples/payments-lite/target \
  .venv/bin/python -m rl_defense.live.pilot_gate --out results/pilot-gate
```

If the candidate fails, the result is committed as a failure and the gate stays blocked.
These scenarios are then exposed and may not be reused as fresh.
