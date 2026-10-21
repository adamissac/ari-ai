# Bounded duration screen — fixed before train/validation execution

Owner authorized short/long training comparisons and one duration-aware policy test.
This is a deterministic heuristic screen, not a trained RL policy or a v11 run.
No holdout directory may be loaded/executed. V6 and its actual registry remain unchanged.
Commit and push the source and this plan before execution; freeze source during the run.

## One fixed candidate; no grid or retries

Reuse the existing `rules_policy(long_mode="outsider", long_target="all")` behavior.
Use block_anomaly=0.0, block_min_volume=0.0 and isolate/rate-limit/monitor thresholds1.1
(disabled on normalized observations). With flagged unauthorized requests, choose long
blocks when observed flagged-own/authorized traffic share equals zero, short otherwise;
if no short action is valid, existing controls persist and the disabled fallback noops.
Observed lack of authorized traffic is a heuristic, not proof a principal is an outsider.
No hidden attack label, future traffic, identity name or scenario name enters decisions.
No new observation/action schema, gateway control, serving fallback or permission.

Comparators: always-short, always-long, actual registry v6 and the previously tuned
v10 threshold rules (fixed saved parameters, no tuning). Candidate/reference choices
are fixed regardless of train results. No additional candidate if this one fails.

Run train_v8 first, first8 registered seeds for each of7 scenarios and5 policies:
280 episodes. Then run all16 registered seeds in each of3 val_v10 scenarios for all5
policies:240 episodes. Total520 episodes ×30 windows. Keep all raw metrics and traces.
Validation is an existing, previously used selection set, not fresh held-out evidence.
Do not run old holdouts or create/use a v11 holdout in this screen.

## Decision before preparing one possible v11 preregistration

Primary comparison is duration-aware versus **actual deployed v6**, not a weak
long-only control. Require all of:

- Pooled validation availability improvement: paired stratified-bootstrap95% CI lower>0.
- Pooled compromised attack-request fraction difference: CI upper<=0 (zero allowed).
- Every validation scenario has defined compromise rates and candidate point rate<=v6.
- Candidate pooled validation availability meets unchanged85% floor.

Use10,000 paired resamples (seed1), independently within each scenario, retaining its
16 episodes and summing request-count numerators/denominators before computing ratios.
Report pooled and per-scenario means for all5 policies and explicit failures/undefined
metrics. These intervals quantify evaluation-seed uncertainty for fixed policies, not
training-seed uncertainty or a held-out promotion guarantee. No tolerance widening,
post-validation tuning or best-seed selection. Short/long comparisons are diagnostic.

If the screen passes, prepare at most one v11 preregistration with a specific learned
policy intervention and disjoint fresh evaluation data; do not launch it here. If any
condition fails, stop and reconsider objective/control design rather than spend another
six hours. No policy registration or promotion regardless of screen result.

Record exact source/fingerprint/config/checkpoint/registry/plan hashes, commands, runtime,
all records and evidence verification. Failed jobs stay failed; do not silently restart.
