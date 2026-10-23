# Resource-exhaustion feasibility 001 — BLOCKED DRAFT

Status: proposed, not approved for comparative execution or training. Owner
explicitly authorized implementation and bounded unit instrumentation only when
numeric study constraints/sample/compute values remain unapproved. No formal
comparison is run. These proposed values precede instrumentation results.

Question: can finite-budget adaptive rate limiting improve the availability/resource
tradeoff over strong conventional policies in a bounded finite-worker service?
This is distinct from authorizing payment reads. All jobs are permission-valid;
resource-abuse labels are synthetic evaluation truth, never policy inputs.

Proposed fixed design: resource-queue/0.1; two workers, queue12, eight service ticks
per decision, deadline24 ticks, four observable source slots, two routes. Work demand
is integer worker-ticks, not measured CPU. Control delay1 window, duration2 windows,
cooldown2 windows, quota route2/source3 per window, application overhead1 worker-tick.
Fixture application budget4 is an engineering cap, not an approved safety budget.
Freeze code/config, generator, baselines, normalization and outcome definitions in
an immutable source/config/dependency manifest before comparative execution.

Six scenario families: stable, legitimate_burst, low_exhaustion, high_exhaustion,
shifting, mixed. Parameters are in resource/workload.py, not selected from outcomes.
Offered traffic uses its own seeded stream and is paired independently of controls;
patterns shift exogenously, not as a measured strategic attacker response. Include
costly authorized work, benign high-volume sources and overlapping source identities.
No family is reserved final holdout; these are development/feasibility proposals.

Proposed feasibility sample:20 independent workload seeds per family, four fixed
baseline policies plus the always-on conventional reference,30 decision windows per episode;600 episodes/18,000 decisions.
Proposed compute cap: one CPU process,512MiB measured process RSS,600 wall seconds;
stop/incomplete if exceeded, not silently extend or replace seeds. These numbers
and all safety thresholds/sample/compute details require explicit owner approval.
Seed identities proposed0..19 are feasibility-only; do not later call them fresh.
No final holdout is authored, generated or read in this phase.

Baselines: noop; static rate limit (maintain per-route limit when feasible);
threshold adaptive (fixed pressure/latency thresholds); resource-aware hysteresis
using offered work, queue, observed throughput, timers and budget. Same physical
quota/duration/delay/cooldown/application cap; all targets from past observable
activity. No policy sees job labels, future arrivals or remaining work of unseen jobs.
The full-horizon static reference has different duration capability and is reported
separately with all active-time costs; a gap only against a handicapped static policy
is insufficient for a training GO. Frozen v6 and prior69-channel diagnostic schema
are incompatible and excluded.

Outcomes, reported separately by family and seed: adversarial consumed worker-ticks;
legitimate offered/completed/rejected/timeout/pending counts; completed latency sums
and count (null mean when none); queue depth/max and exhaustion ticks; utilization;
applications, active-control ticks, overhead units, recovery time (censored if no
recovery by endpoint). Completion fraction by fixed horizon is a lower bound while
jobs remain pending. Never count noncompletion/pending as known attack prevention.
Report all offered jobs and reconcile terminal states including right-censoring.

Primary feasibility tests: interventions change measured admission/consumption;
queue/timer carryover changes later outcomes; aggressive limits harm legitimate load.
A heuristic performance gap requires the approved same-scenario comparison; unit
mechanism checks alone cannot establish a gap or RL superiority. Report dominance
by any deterministic rule rather than selecting a favorable family/seed.

Proposed uncertainty: paired cluster bootstrap over whole workload seeds, stratified
by family;2000 resamples,95% intervals, reporting all predeclared endpoints, no
window-level pseudoreplication or post-hoc best-seed selection. Proposed minimum relevant effect:10% relative reduction in adversarial consumed
work versus the strongest safe fixed baseline; no claim if its denominator is zero.
Proposed per-family safety requirements: legitimate completion lower bound >=90%,
rate+capacity denial fraction <=5%, timeout fraction <=5%, completed mean latency
<=16 virtual ticks, <=4 applications, <=64 active-control ticks and <=4 overhead
worker-ticks. All are UNAPPROVED proposals, not selected to pass observed results.
Pending requests/right-censoring and zero denominators cannot certify a pass.
The full-horizon reference exceeds64 active ticks by design; report its complete
cost separately, and ask whether the operational constraint itself is defensible
rather than manufacturing a learning advantage. Owner may reject these values;
freeze the accepted values before any formal comparison, never relax after results.

Stop and retain failures/partial records for invalid action/mask, inconsistent
resource/request accounting, cutoff/label leakage, deadline/control cleanup bug,
missing required telemetry, safety threshold violation or compute cap. One fixed
launch only after approvals; no unfavorable-only reruns, replacement seeds, sweeps,
or interim tuning. A separately approved new registration is required for any retry.
Archive source/versions/config hash, seeds/family/split, complete job traces and
control ledger, masks, proposed/applied actions, probabilities, raw reward/cost
channels, terminal flags and errors. Unit fixtures are labelled non-study and
ineligible for replay training. Collection and training approvals are separate.

Generator burst phases and shifting-source dwell are stochastic and private, not
deterministic episode-clock schedules. FIFO ties are randomly mixed independently
of policy and generator labels. This avoids an artificial calendar/label-priority
advantage; it does not establish realistic adversary adaptation or RL superiority.


Terminal accounting proposal: after30 decisions, stop all controls and run at most
ceil(deadline/window)=3 no-arrival/no-control settlement windows. Include their raw
consumption/completion/timeout outcomes in full-lifecycle comparison totals, with
decision-phase and settlement-phase metrics reported separately. This prevents
claiming saved resource simply because work was deferred beyond the horizon.
Decision count remains18,000; maximum physical windows19,800. Any pending work after
the deadline-bound drain is an accounting failure, not a successful censored result.
The helper is unit-tested but no formal study or drain-based comparison is run.
Nonzero denial allowances here would require fresh explicit acceptance for this
resource-service task and cannot weaken prior zero-violation payment-read limits.
