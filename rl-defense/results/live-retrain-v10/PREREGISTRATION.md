# V10 preregistration — balance demonstrated actions

Status: preregistered for a future run; no v10 holdout has been executed and no learned
policy is promoted. Commit and push this file, configs and runner before launching.

## Motivation and limits

Saved v9 teacher data contain 3,652–3,696 noop rows out of 4,200 per seed (about87%).
The worst failure has valid principal-block actions during compromised windows but
chooses noop. This suggests a demonstration-frequency problem; it does not establish
causality. V9 mixed rotation also regresses against v6. Its exposed holdout is analysis
material only and is never used as fresh evaluation again.

## Controlled intervention

Two arms, uniform (control) and action-balanced (candidate), each fixed seeds0–4.
The only arm difference is `--balance-demo-actions`: choose an observed teacher action
class uniformly, then a genuine demonstration row uniformly within that class. Apply
this to both pretraining and the demonstration part of online batches; agent replay
stays uniform. No action is invented, no hidden attack label enters sampling, and the
25% demonstration share stays fixed. Default existing behavior remains uniform.

Both arms use unchanged train_v8 (seven scenarios), the same teacher grid and selection
(two episodes/scenario), 20 demonstration episodes/scenario =4,200 rows, 5,000 pretrain
updates, 150,000 online transitions and updates, batch64, demo fraction0.25, lambda1,
margin0.8, lr3e-4, hidden128×128, gamma0.99, target sync1,000, replay100k,
epsilon0.3→0.05/75k. Same severity/platform/delegation-aware loop and reward as v9.
Snapshots step0/every15k; same eight validation episodes/scenario, noop margins
0/0.1/0.2/0.3/0.5, unweighted scenario-mean score, first maximum wins. Each seed retains
both selected snapshot lineage and the complete experiment, including step0 selection.

Fresh val_v10 contains quiet, persistent outsider and mixed rotation regimes at
28000/28300/28600 (16 seeds each). Fresh holdout_v10 uses distinct timing/intensity
combinations and seeds43100–43199,43200–43299,43300–43399 (100 episodes each).
These exact config bytes are frozen before training. No held-out episode runs in CI,
smoke tests, selection or interim analysis. Both arms see identical validation/holdout
seeds. No additional tuning after held-out exposure; failed jobs stay failed, no seed
replacement, retries or best-seed selection. Technical recovery needs a written record.

## Comparators, measurements and decision

Actual registry incumbent must still be v6 SHA
`8113a37f4ff9360a9efed2e9f499c4b2ae36e97bfb78372436f97da106fc05f1`.
Fixed v8 SHA `ec8b5042fd56d2f75c6791b89152b57f4a6870c3656321b9f554056b4c0fc528`
and each same-seed v9 checkpoint are references, hash-pinned before launch. Report
candidate, v6, v8, matched v9, threshold rules, noop, random-valid, always isolate,
short principal block, long principal block and top long block: 11 policies ×3×100
paired episodes/run, ten runs =33,000 episodes. Retain all metrics and raw trajectories.

Primary support requires (1) the 95% bootstrap CI lower bound of the action-balanced
minus uniform paired seed-mean return >0; (2) balanced minus actual v6 return CI lower
bound >0; (3) every balanced seed passes all unchanged promotion.yaml checks. Otherwise
report unsupported. No study result selects a model or provides human approval.
Six metrics: return, compromised attack-request fraction, benign availability, quiet
false disruption, quiet disruptive-control duty and non-noop actions/window. Use all
five paired seed means,10,000 bootstrap resamples (seed1), two-sided paired t-tests
(n=5), Holm correction across the six arm-comparison metrics. Publish per-scenario
values and all per-seed gates, including losses and undefined values (never a pass).

Secondary: each model's train-only platform checks, two cases/280 windows, quiet noop
≥95% and flagged principal block≥90%; mapping agreement reported separately. Retain the
worst candidate-minus-incumbent paired episode and both raw traces. No held-out reruns
for analysis. Record source, runtime, config/preregistration/registry/reference hashes,
exact commands, complete experience and model hashes. Verify saved evidence by streaming.

This is the owned, isolated in-process payments-lite lab, not the canonical simulator
benchmark or proof of real-world effectiveness. Small n, fixed-reference uncertainty,
importance of disruption costs and possible over-weighting of rare teacher mistakes
are explicit limitations. Expected compute: roughly twice v9's 3h7m with five CPU workers.
