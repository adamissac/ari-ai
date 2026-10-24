# Threat, physical accounting, observations and limits

This work supplies a finite-service model, not evidence of measured production CPU.
Each worker can execute one work unit per virtual tick; queue admission is FIFO up
to workers+waiting_capacity. A request has an observable source/route and an internal
work demand. The policy sees work consumed in the preceding window, not future
request cost/labels or unprocessed residual demand. Two sources can generate abuse
while also making legitimate requests; shifting traffic changes sources with a private stochastic dwell. Identity is fixture-authoritative, not a claim about trustworthy
Internet IPs or NAT attribution. All jobs are permission-valid. The prior payment
read guard, provider, checkpoints and evidence are unchanged and outside this model.

All requests have one terminal/pending outcome: capacity reject, rate reject,
timeout, completion or right-censored pending. Accepted counts include pending and
later timeouts. Partial consumed work survives timeout in the ledger; no resource
units are erased by deleting a job. Completion at the exact deadline is timely;
expiry runs before the next processing tick and at the observation boundary.
Events retain ordered offer/admission/work/completion/expiry records. Request IDs
and the full ledger support independent reward/cost recomputation.

No hidden random success/failure bonus exists. Failures are capacity or deadline
outcomes; arbitrary application500s, memory allocators and network loss are not
modeled. Capacity exhaustion counts full-capacity ticks, while queue depth/max,
inflight, work+overhead utilization and completed latency/service/wait sums are
separate. Queue-pressure recovery is first subsequent inflight<=worker_count; it
can occur through timeout and is never a standalone security-success metric.

## Capacity-based workload and baseline design

Legitimate cheap work is uniform1..2 (mean1.5), expensive work3..6 (mean4.5), with30%
expensive requests: expected2.4 units/request. Base5 requests/window means12 work
units versus16 capacity. Burst9 requests with on/off probabilities0.2/0.4 (stationary fraction1/3)
averages15.2 units/window;
mixed6 legitimate requests averages14.4. These analytic design calculations avoid
making normal legitimate demand intrinsically exceed service supply. Random peaks
can still overflow or expire; means are not an availability guarantee.

The fixed expensive-route quota2 follows the remaining expected capacity after
base cheap demand (5*0.7*1.5=5.25 units): floor((16-5.25)/4.5)=2. This is an engineering
configuration, not fitted to comparison outcomes. Source quota3 is a proposed
request-count cap, not an oracle cost estimate. Both route/cost classes overlap
labels. Initial development defaults were revised analytically before any formal
study; source commits distinguish the versions. No population result was used.

The four budget-matched policies share actuation, source-target selection, quota,
delay/duration/cooldown, cap and sensing. The resource-aware rule responds earlier
to pressure and considers observed concentration and denials; it receives no
legitimate/attack label. Static scheduling is the fixed conventional rule under
that finite intervention cap. An additional persistent static-route reference is
not handicapped by ephemeral duration; its one startup application, full active
duration and overhead are all charged. Its duration capability differs and its
adaptive-budget feature is unknown. Do not pool its return as an equal-capability
arm or claim RL superiority solely against the weaker budgeted static variant.

## Causal observation specification

Version resource-observation/0.1:35 raw normalized values +35 known bits +3 mask
bits =73. All sources are the service's completed-window counters or current
operator-visible control/queue/budget state. Counts and normalization denominators
come from frozen config, never evaluation fitting. Source/route slots are public
fixture labels; no attack identity/type/scenario/seed enters the vector.

- arrivals, accepted, rejected, completed, timeouts, limit_denials, capacity_denials:
  previous-window counters / (64+workers+queue_capacity). Before first window or
  missing telemetry these are unknown. Offered workloads are bounded64/window.
- queue_depth and inflight: current waiting/total jobs over configured bounds;
  always known because the service owns the queue, independent of telemetry loss.
- latency_mean: completed-response latency sum/count/deadline; unknown if no
  completions. Utilization is measured work+overhead / worker capacity.
- source_arrivals_0..3 and route_arrivals_0..1: observed volume/64. Corresponding
  work channels: consumed units / per-window worker capacity. Missing telemetry
  clears their known bits and masks out context-dependent actions.
- active_route, active_source, pending_windows, remaining_windows, cooldown_windows:
  local actuator ledger flags and residual times. Pending/duration are distinct;
  cooldown begins at expiry. Values normalize by their configured timer caps.
- budget_remaining, intervention_count and time_remaining: local application cap,
  applied interventions and finite-horizon clock. Full-horizon reference uses its
  own duration scale and unknown adaptive budget; the profile is recorded separately.
- controlled_source_0..3: pending/active source target one-hot, all zero if none.
- Last three bits: independent feasible noop/route/source masks. No-op is always
  feasible during a live episode. No new control can activate beyond its horizon.

Known=false encodes a zero filler, not a measured zero. Every field is internal
research-only, trustworthy only as simulated service instrumentation. No provider,
client assertion or agent text can widen an action permission. The vector is a
partially observed history summary, not proof of Markov sufficiency.

Snapshot event sequence < action sequence < resulting service event sequences <
next snapshot cutoff. Sequence numbers order availability; virtual tick measures
service time. This removes same-tick ambiguity. Future scripts/hidden labels cannot
change a prior observation; immutable recorded vectors are never backfilled.
Ground-truth labels occur only in post-action metric/reward calculation and raw
metrics-only request traces. The policy API accepts the vector alone, never info.

## Objective and costs

Primary reward: negative modeled adversarial work actually consumed this window.
Compare raw totals later under an approved paired design; it is not individual
counterfactual prevention, permission repair or proof of real attack success.
Preserve legitimate rate/capacity denials, timeouts and latency sums separately,
plus applications, active ticks and overhead. Reporting no completed legitimate
requests cannot become a low-latency success; retain denominator and pending count.
No investigation/logging action is included because no measured information effect
exists. No monetary cost, real-world CPU or customer SLA is invented.

Application overhead is an actual unavailable worker slot on the first tick of
that window. Controls affect admission after their delay, then queue work and
latency persist even after expiry. They do not magically erase already admitted
work. This establishes a sequential mechanism and collateral effects in unit
fixtures only, not a heuristic gap or RL advantage. Numerical safety requirements
are proposed in PREREGISTRATION.md and remain unapproved.

Generator burst phases and shifting-source dwell are stochastic and private, not
deterministic episode-clock schedules. FIFO ties are randomly mixed independently
of policy and generator labels. This avoids an artificial calendar/label-priority
advantage; it does not establish realistic adversary adaptation or RL superiority.
