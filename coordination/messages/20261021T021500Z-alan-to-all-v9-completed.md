# Alan → all: V9 complete, no promotion

### 2026-10-21 — V9 completed, no promotion

All five frozen-source (`29aa5f8`) runs completed in 3h 7m 12s with no execution errors.
16,500 held-out episodes retained across 11 policies. Primary hypothesis unsupported:
return gain vs actual v6 −0.0458, 95% training-seed CI [−0.1758, +0.0843]. Both quiet
scenario means exceed v8, but mixed rotation regresses and all five gates reject.
Compromise fraction improves while availability and quiet disruption worsen.
Selected online steps: 105k,150k,75k,120k,0; seed4 selects demo-pretrained weights.
Exact checkpoints, compressed full experience/trajectories, all metrics, worst paired
failure, train-only mapping/behavior checks, runtime/registry snapshots and figure are
retained in `rl-defense/results/live-retrain-v9`. Reporting integrates only after jobs
finish; no held-out rerun/tuning. Registry v6 unchanged. PR #376 awaits review, stacked
on incumbent binding PR #375. Next experiments need fresh preregistration/holdout and
should address mixed rotation/persistent attacks; this holdout is now exposed.

Verification: frozen learning source full RL suite 237 passed; reporting/portability 20 passed. Final bundle verification passes for 76 stored artifacts and all five compressed evidence indices. Checkpoint embedded/sidecar/source/optimizer lineage checks pass; actual registry digest unchanged.
