# Proposed feasibility gate after Phase 1

Status: proposed; not an execution authorization or a registered experiment.
The owner requested continuation after Phase 1. This document makes the next
research decision reviewable without starting Phase 2 or choosing safety budgets
from observed results. No training, collection, control implementation or serving
change is included.

## Decision to resolve first

Can a deterministic, authorization-aware control prevent unauthorized payment
reads while preserving own-object and explicitly delegated reads? If an ordinary
application authorization repair solves the problem, prefer that repair. A learned
policy must demonstrate additional value before it is justified.

The current principal-wide short-block budget is insufficient: two interventions
can expire while compromise continues. An intervention count is not a bound on
cumulative unauthorized reads or legitimate denials. The Phase 1 no-go remains.

## Proposed state and behavior record

Extend the existing research adapter only after contract-owner review. Do not
create a second canonical experience schema. A proposal should describe:

- Current control state, remaining control duration and elapsed time; action and
  cumulative measured cost history; the decision-time capability mask.
- Observable principal/resource ownership and explicit delegation evidence with
  provenance and freshness. Missing ownership or grants remain unknown.
- Separate own-object, valid delegated and other legitimate request outcomes;
  denied requests and non-denial failures remain distinct.
- Behavior-policy identity, selection rule and known action probability. A
  deterministic policy may record probability one for its chosen action and zero
  for others; this does not supply support for unchosen actions.
- Observation-history encoding and its version. Generator intent, future traffic,
  attack labels and hidden schedules remain metrics-only.

Producer: owned lab instrumentation. Consumer: research adapter and descriptive
feasibility verifier. Canonical shared-contract integration is proposed, not
implemented. Retain source, scenario, split, seed and complete trajectory identity.

## Proposed independent control checks

Specify the control before collecting any comparison data. Keep existing action
indices and production behavior unchanged. Independently execute the following
checks in an authorized, isolated fixture if implementation is later approved:

1. An unauthorized foreign-object read is rejected.
2. The owner can still read its own object.
3. An explicit valid delegate can read only covered resources.
4. Expired or revoked delegation is rejected without using stale permission facts.
5. Missing or contradictory identity/ownership context triggers explicit abstention
   or the separately approved application authorization behavior; never infer a grant.
6. Control expiration, reset, repeated actions and two principals cannot bypass
   the rule or transfer a block/permission to another identity.

Verify must use independent fixtures and immutable candidate artifacts. A passing
lab fixture is not evidence of production safety or generalization.

## Required owner decisions before preregistration

All values below are **unset**. No defaults are inferred from Phase 1 results.

- Cumulative legitimate-denial budget B, its units and aggregation horizon.
- Intervention budget I, residual control duration semantics and reset behavior.
- Maximum compromise and minimum legitimate availability for every scenario,
  including separate own-object and delegated request criteria.
- Confidence level, interval method, minimum independent units and the rule for
  treating inconclusive intervals or unknown attribution.
- Dataset lineage, permitted splits and genuinely unexposed evaluation scenarios;
  formerly exposed holdout cannot be relabeled as fresh.
- Fixed comparison policies, sample counts, compute limit and stopping rule.
  No automatic retries, replacement seeds or interim-result tuning.

## Go/no-go sequence

First agree on the state/behavior proposal and independent control checks. Then
approve and preregister one bounded deterministic feasibility comparison with
complete source and configuration pins. Establish feasible controls and data
support under the agreed thresholds before proposing any learned algorithm.
Only a separate, subsequent authorization can start one constrained DDQN ablation.
CQL is not the automatic next step, and neither approach may bypass hard scope,
authorization or capability checks. Keep v6 and all historical evidence unchanged.
