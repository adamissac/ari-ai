# Alan → all: v10 complete, all candidates rejected

### 2026-10-21 — RL-V10-001 completed, no promotion

Completed uniform/balanced seeds0–4 from frozen source `a98899d` in5h58m17s
(before final diagnostics), no execution errors;33,000 held-out episodes retained.
Balanced-minus-uniform return +0.05919 (95% training-seed CI +0.03335 to +0.08713;
Holm p0.0895); balanced-minus-v6 +0.29080 (CI +0.27056 to +0.31045). Primary
hypothesis unsupported: all ten candidates reject; every balanced seed has a scenario
regression, four fail availability, three fail static-rules comparison. Compromise
improves but availability/quiet disruption worsen. Train-only diagnostics pass for
all ten; all saved evidence verifies and checkpoints reload. Worst saved failure:
uniform seed2 persistent43203,84/84 compromised vs v6 0/84. No holdout reruns,
retries or promotion. Real registry digest remains c3455933…; v6 stays deployed.
Results/provenance: `rl-defense/results/live-retrain-v10/PROVENANCE.md`.
Future experiments need fresh preregistration/holdout; no follow-up run launched.

Post-run focused validation: 12 tests passed in 23.20s; Ruff lint/format passed.
