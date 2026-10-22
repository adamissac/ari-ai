# RL-CMDP-001 Phase 1 execution boundary

Freeze and publish code/this plan before baseline execution. This is a foundation
check, not a learned-policy experiment, promotion gate or v11. No Phase 2 work.

Run five fixed policies on the first four registered seeds of each of seven
`train_v8` scenarios: 140 episodes, 4,200 scored windows, plus reset warmups.
Never load or execute holdout. No validation tuning, replacement seeds or retries.
Noop, saved v10 tuned rules, fixed short principal block, frozen v6 weights and
fixed cost-aware rules all see the same capability-restricted live_v3 mask.
The shield removes no-traffic gateway/auth/db node actions, live escalation
(timer only), and reassessment (scripted severity change, no target repair).
Monitoring on api/payments remains available for its observable sensing effect.
This **changes action-selection semantics** for v6/rules. Label them shielded;
never compare these measurements to original v6 promotion numbers as a ranking.

Use existing delegation-aware detector and platform-derived severity context;
record all LoopConfig defaults/overrides and original lab outcomes. Cost-aware:
require payments finding severity>0 and available flagged-principal short block;
at most two short block actions/episode; never long, isolate, rate limit or
escalate. This heuristic is fixed before seeing results; it does not guarantee
an expected damage budget or recognize intent. It receives only obs and mask.

Report negative compromised-read counts and separate legitimate-defense-denial
counts, intervention counts, request compromise fraction, benign availability,
quiet-window false disruption and discounted/undiscounted cumulative cost.
Gamma=1, finite30-step horizon, bootstrap seed17,2,000 resamples. Resample whole
seed clusters, stratified by scenario membership; shared-seed scenarios stay in
one cluster. Never resample windows as independent units. Undefined denominators
and unknown costs stay null. Four seeds/scenario are an engineering check, not
adequate evidence of learned-policy superiority or rare-event safety.

Retain raw request records and transitions, exact scenario configs/seeds, original
checkpoint/manifest and fixed-rule hashes, dependencies, source commit/tree and
full relevant source hashes. Verify raw requests→counts→separate objectives→all
per-scenario/pooled metrics→saved summaries. No registry writes, checkpoint changes,
serving integration, new actions/indices, paid models, external traffic or deployment.
Only the owned payments-lite ASGI app is executed. Preserve all historical files.

Separately adapt compatible existing **training** logs read-only after verifying
caller-supplied evidence-index hashes. Mark absent first action mask, behavior
propensities and own/delegated denial attribution unknown. Do not use logged
outcomes to evaluate a different policy. Stop after audit, decision, tests and
baseline evidence; no new algorithm implementation or training.
