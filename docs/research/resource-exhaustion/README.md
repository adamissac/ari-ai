# Resource-exhaustion defense — isolated research only

Stage1 mechanism/instrumentation and Stage2 data/protocol preparation implemented.
**Training NO-GO**; formal comparative study awaits explicit numerical approval.
No formal comparison, new trained policy, holdout, promotion or customer integration.
[Blocked preregistration](PREREGISTRATION.md) proposes numbers for owner approval.

PR422 was NO-GO because deterministic authorization addressed the modeled BOLA
endpoint and no measured residual resource/diagnostic task or candidate dataset
existed. PRs388/394/396/407/410/414 remain historical foundations, with all original
artifacts and checkpoint identities preserved. This new task never changes read
permissions. Every modeled job is permission-valid; some abuse finite capacity.

## Model and threat

A repository-owned virtual-clock FIFO service executes finite processing work:
two workers, twelve waiting slots, integer worker-ticks, bounded job cost and a
request deadline. Arrival order, processing, admission and completion are executed
by Service, not assigned from a reward table. It is a queueing simulation, not an
HTTP deployment or calibrated CPU/latency measurement. Worker count, costs, queue
bounds, deadlines, control overhead and arrival processes are explicit assumptions.

Four observable synthetic source slots and two public routes carry both legitimate
and resource-abusive work. Legitimate work includes expensive requests and bursts;
abusive work can share sources/routes and shift exogenously. No omniscient target
selector or hidden generator label enters observations. Finite queues, unfinished
work, controls/cooldowns and remaining budget carry consequences across decisions.
This demonstrates a sequential mechanism, not that RL beats conventional controls.

## Actions and baselines

New local resource-actions/0.1 indices:0 noop,1 temporary rate limit on expensive
route1,2 temporary limit on the source with highest **previous measured consumed
work**, falling back to observed offered volume, lowest-slot tie break. No old
production/v6 indices change. Logging/investigation are omitted: no demonstrated
information/completion effect justifies them.

Application costs one modeled worker-tick immediately. Activation is delayed one
window, duration2 windows, cooldown2 windows; only one pending/active control at a
time. Four applications is a unit-fixture engineering cap, not an approved safety
budget. Quotas reset each window (route2/source3 matching offered attempts). Quota
is consumed before backend admission, including requests later capacity-rejected.
Independent masks/step checks reject unavailable choices; no silent noop replacement.
Controls expire and episode/reset cleanup prevents residual execution.

Four fixed baselines consume only normalized observable vectors: noop, static
fixed-route schedule under common caps, threshold adaptive, resource-aware rule.
A supplemental always-on static-route reference uses one startup application and
full-horizon duration. Its different capability/cost is explicit; it is not pooled
as an equal-capability primary arm. A later RL claim must not rely on handicapping
this conventional reference. Neither variant is tuned/evaluated across scenarios here.

## Observation and outcome boundaries

resource-observation/0.1 has35 scalars,35 known bits and3 mask bits =73 channels.
Sources: completed-window arrival/admission/completion/denial/timeout/latency and
consumption counters; current queue/inflight counts; control kind/target/timers,
cooldown, remaining application cap and finite-horizon time. Source/route vectors
contain observed volumes/work, not labels or future residual demand. Initial/missing
telemetry and undefined mean latency clear known bits rather than assert measured
zero. Fixed reference has unknown adaptive-budget channel. Physical normalization
comes from config bounds, never fitted on evaluation data.

A monotonic event sequence freezes each observation before its action. Events from
that action/window have larger sequence values; the next observation cutoff is
larger than every included event's availability sequence. Physical service ticks
are separate units. Scripted future arrivals and hidden labels cannot change an
earlier vector. The vector is partial; Markov sufficiency is not established.

Reward is negative actual **modeled adversarial consumed worker-ticks**, a metrics-only
post-action signal. It is not individual causal prevention, authorizing a read or a
bonus for setting a flag. Costs remain separate: legitimate rate/capacity denials,
timeouts, completed latency sums, applications, active-control ticks and overhead.
Blocking all work causes legitimate damage, not success. All ratios retain their
counts; absent completion denominators remain undefined. Pending jobs at episode
end are right-censored, not fabricated failures/completions. Queue-pressure recovery
can occur through expiry and is not by itself evidence of healthy availability.

[Detailed threat/accounting/observations](DESIGN.md) · [Stage2 readiness and approvals](TRAINING_PREPARATION.md).

Core Gym contract check uses a feasibility-mask-aware action sampler because the
generic Gym checker does not consume masks. Invalid actions remain independently
rejected; full route/source action effects are exercised in the unit tests.
