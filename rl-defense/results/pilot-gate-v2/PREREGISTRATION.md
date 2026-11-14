# v11 candidate and pilot gate v2: pre-registration (committed before any v11 run)

Decided with Alan (RL owner, with Adam) on 2026-11-14, after frozen v6 failed the first pilot
gate (`results/pilot-gate/REPORT.md`).

## The earlier "do not launch v11" decision

`results/v10-followup-diagnosis/README.md` said not to launch v11 without an evidence-backed
fix and a testable prediction. This run is launched with the owner's approval and states both.

**Evidence.** (1) In the first gate v6 trailed the rules only where three attackers switched
per request (compromise 0.129 against 0.083), and on the bookkeeper-insider scenario it let
62% of authorized delegated reads through with legitimate traffic blocked in 71% of
attack-free windows. `train_v3` has no scenario with more than two attackers or per-request
switching, and one scenario with a delegate attacker against a single victim. (2) The v10
diagnosis found the selector takes the best validation return even when that snapshot is
below the 0.85 availability floor.

**Fix.** (1) `train_v11` = the five `train_v3` scenarios plus `train11_trio_per_request` and
`train11_delegate_multi_victim`. (2) Snapshot selection prefers (snapshot, margin) pairs
with validation availability >= 0.85 and takes the best return among them
(`OnlineConfig.min_val_availability`). Everything else is the v6 method and settings: DQfD
online in the live lab, 20 expert episodes per train scenario, 5,000 pretraining updates,
150,000 environment steps, seed 0, the v4 loop, action space live_v3, fixed finding
severities. Rules are re-tuned on `train_v11` with the unchanged procedure
(`tune_rules_v3`) and are both a teacher candidate and the gate's incumbent.

**Prediction, checked on validation only** (`val_v11` = the four `val_v4` scenarios plus
`val11_trio_switch` and `val11_delegate_two_victims`, 8 episodes each): the selected
snapshot has pooled availability >= 0.85 and its mean return is not below the re-tuned
rules' on any of the six validation scenarios. **If the prediction fails, the gate is not
run**, the v2 gate scenarios stay unexposed, and the result is reported as a failed
prediction.

## Gate v2 (only if the prediction holds)

Scenarios: `configs/live/pilot_gate_v2/` (gate2_switching_quartet seeds 41800-41829,
gate2_both_bookkeepers_rogue 42200-42229, gate2_busy_day_faint_insider 42700-42729,
gate2_outsider_from_start 44200-44229), written before training and disjoint in name and
seed from every other directory. One run, every policy on the same episodes:

```sh
PYTHONPATH=.:../shared:../standards:../examples/payments-lite/target \
  .venv/bin/python -m rl_defense.live.pilot_gate --out results/pilot-gate-v2 \
  --scenario-dir pilot_gate_v2 --candidate results/live-retrain-v11/candidate_v11.pt \
  --candidate-sha256 <sha> --rules-tuning results/live-retrain-v11/rules_tuning.json \
  --rules-tuning-sha256 <sha> --reference-v6
```

Thresholds are the ones approved for the first gate, unchanged: the eight checks in
`results/pilot-gate/PREREGISTRATION.md` (promotion.yaml with the re-tuned rules as incumbent,
plus delegated success >= 0.85). Frozen v6 runs on the same episodes and is reported only.

A pass does not promote anything. It makes v11 a candidate for the owner-approval step; RL
stays shadow-only and recommendation-only, and serving v11 in the backend shadow path is a
separate reviewed change. One training seed: a pass is evidence about this checkpoint, not
about the method's seed variance.
