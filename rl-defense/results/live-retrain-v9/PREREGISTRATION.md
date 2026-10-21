# V9 preregistration — quiet validation, incumbent v6, five training seeds

2026-10-20. Commit and push this file/configs/runner before any training. Prerequisite
PR #375 remains subject to review; v9 is stacked on its tested fixes. No policy is promoted.

## Motivation and hypothesis

V8 added quiet training traffic but selected on val_v4, which lacks it; it still trailed
noop on rare_delegate_runs. Its historical gate pass used a fresh simulator baseline,
not incumbent v6. Old holdouts are exposed and will not be re-used for this experiment.

Hypothesis support requires BOTH: candidate-minus-incumbent overall return CI lower bound
>0 across five training-seed means, AND candidate mean return≥fixed v8 on EACH new
low-intensity holdout scenario. Otherwise report unsupported. This is not a pure causal
ablation: fixed v8 is one prior checkpoint, while this cohort contains five fresh networks.

## Fixed learning method

- Train `train_v8` unchanged; fresh networks for ALL training seeds0–4. No replacement,
  best-seed choice, early stopping or post-holdout tuning.
- Selection change: `val_v9` = four byte-identical val_v4 YAMLs plus
  val9_quiet_delegate and val9_faint_outsider. Existing unweighted scenario-mean rule,
  eight episodes/scenario; snapshots at step0 and every15,000; margins0,0.1,0.2,0.3,0.5;
  first maximum wins ties.
- Same loop: live_v3, platform severity context, grant-aware detector, c_disrupt1.0.
- Same OnlineConfig defaults: 20 demo episodes/scenario (4,200 transitions), 5,000
  pretraining updates, 150,000 online steps, epsilon0.3→0.05 over75,000, one update/step,
  batch64, demo fraction0.25, DQfD lambda1/margin0.8, lr3e-4, hidden128×128, gamma0.99,
  target sync1,000, replay100,000. Same budget for every seed.
- Same train-only rules grid/teacher selection, two episodes/scenario. No tuning on val
  or holdout. All policies use identical scenarios/episode seeds/loop overrides.
- Up to five CPU processes, one Torch thread each; record hardware, source SHA and argv.

## Actual incumbent

Use read-only the existing registry under the owner's checkout at
`.claude/worktrees/mystifying-hofstadter-c5aaf7/rl-defense/runs/live/registry.json`.
Deployed v6: pol_8113a37f4ff9360a; exact checkpoint SHA256
8113a37f4ff9360a9efed2e9f499c4b2ae36e97bfb78372436f97da106fc05f1.
Verify actual checkpoint and registry bytes; fail if incumbent changes. Do not initialize
a fabricated registry or approval. `run_study.py` never writes this registry.

Policies: incumbent v6 (gate comparator), candidate, train-tuned rules, noop,
seeded random-valid (independent RNG=training_seed+91019, samples only valid mask),
always-isolate-payments, all three principal-block baselines, fixed v7 and v8 references.
References are report-only. All policies are reported, including metrics where RL loses.

## Fresh holdout_v9

100 paired episodes/scenario/policy/training seed. New names and unused seed ranges:
- quiet_rogue_reconciler,40300–40399: Dave (Erin's delegate) attacks Carol,2/window,
  p_start0.035/p_stop0.55,10 benign/window; rare attacks with legitimate opportunity cost.
- faint_outsider_reconciliation,40700–40799: rotating Mallory attacks Alice/Dave,
  1/window,p_start0.07/p_stop0.2,10 benign/window; heavy delegated reconciliation.
- mixed_delegate_rotation,41300–41399: Bob/Erin (Dave's delegates) alternate per request
  against Alice/Carol,4/window,p_start0.18/p_stop0.3,8 benign/window,rotating tokens.

Tests parse/validate these configs but never execute their episodes. All five seeds are
committed to this same holdout before the first starts. Do not inspect a seed's holdout
to alter remaining seeds. Runner refuses output overwrite/implicit restarts; failures
are reported. Recovery needs documented execution-only justification or new preregistration.

## Statistics, evidence and reading rules

- Keep unchanged promotion.yaml, evaluated against incumbent v6 in EACH seed. Report all
  seven checks for every seed; no aggregate result grants approval or selects a seed.
- Six lab metrics: return, compromised-attack-read fraction, legitimate availability,
  quiet-window false disruption, quiet-window defense duty, actions/step. Each aggregate
  uses five training-seed means; 95% bootstrap CIs with10,000 resamples (seed0; paired
  differences seed1). Episode-level per-run CIs are separately labelled, not substitutes.
- Paired candidate-minus-incumbent t tests use five paired seed means, two-sided, Holm
  correction across all six metrics. Report small-n assumptions and every loss.
- Report per-scenario values for every training seed; primary low-intensity comparisons
  above are not inferred from pooled scores.
- Train-only platform check: every selected checkpoint,2 episodes/scenario×10 windows,
  no_findings and bola_high. Secondary behaviour thresholds:≥95% quiet noop,≥90% flagged
  principal blocks. Report actual mapping agreement even if the behaviour fails.
- Retain worst candidate-minus-incumbent episode with training seed/scenario/eval seed
  and raw trajectory, alongside the aggregate report. No favorable episode selection.
- Save each checkpoint/manifest, full and selected-prefix training experience, complete
  validation history, rules grid, per-episode metrics, gzip raw holdout trajectories,
  promotion report and hash-pinned evidence index. Aggregate all five seeds or refuse.

Scope discrepancy: docs/17 specifies a different simulator environment/metrics and five
seeds; past live-lab runs used one seed. This study adopts its five-seed/100-episode
safeguards with disjoint LIVE seed bands and request metrics. ADR-0018 proposes the lab
extension; this is experimental lab evidence, not a claim of satisfying the unchanged
DefenseSimEnv-v0 benchmark. No simulated-stage impact/TTC metric is invented. Results do
not establish real-world effectiveness or permission to execute production controls.

## Reproduce

From rl-defense with the existing Python3.12 RL virtualenv and
PYTHONPATH=.:../shared:../standards:../examples/payments-lite/target:

```sh
python results/live-retrain-v9/run_study.py --workers 5 --registry /ABS/OWNER_CHECKOUT/.claude/worktrees/mystifying-hofstadter-c5aaf7/rl-defense/runs/live/registry.json
```

Runner records source/preregistration/registry hashes and runtime. Reporting/platform
checks happen after all seeds finish. Seen before this registration: v1–v8 historical
reports, old train/val configs, tiny-budget CI smoke on exposed holdout_v2 and split/
aggregation tests. **No policy has executed holdout_v9.** No tuning follows first use.
