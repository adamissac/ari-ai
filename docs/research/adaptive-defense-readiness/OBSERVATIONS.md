# Candidate observation specification

Internal version `adaptive-context/0.1`; not a shared API or saved-policy layout.
32 named raw scalar slots + 32 known-value bits + five candidate action-mask bits =
**69 diagnostic channels**. Values are unnormalized counts/ticks/fractions; normalizing
constants/history encoder must be frozen on train-only information before any learner.
Existing 48/49/55 layouts remain unchanged and cannot consume this vector.

Each entry below inherits schema version 0.1 and this availability/trust contract:
only trusted operator/app/provider/ledger records whose occurrence AND knowledge
arrival are no later than cutoff. Client ownership/delegation claims, LLM statements,
generator labels, future schedules, future outcomes and current-state backfills are
forbidden. All missing/unsupported fields are null with known bit false. Encoded zero
is only a storage filler paired with that false bit; it is never an observed zero.
Known event counts mean counts in the supplied observed prefix, not proof of complete
telemetry. None of these records is currently collected by a new experiment.

ObservedRead binds event ID, request-start/capture, completion and knowledge-arrival
ticks, provider snapshot, actual status, explicit adaptive-denial attribution and
canonical EvidenceRef. The trusted producer must independently verify response
identity before supplying a successful payment event; arbitrary HTTP 200 is insufficient.
This is an internal precondition, not a network DTO or implemented collector guarantee.
No credential is retained. Authority is payments-lite-owned-research and clock domains
must match. Duplicate visible events and incompatible clocks/authority are rejected.
The window is completion-based [window_start, cutoff], available by cutoff. Late
arrivals never rewrite frozen vectors. Permission classification uses the immutable
request-start snapshot; later expiry/revocation cannot relabel a historical read.
Unknown age/coverage stays explicit; revocation at a later time is a later event.

Feature-level source / producer / status (all availability and trust rules above apply):

0. `request_count` — count of completed available events, not total offered traffic. Producer/source: event collector. Coverage/missing: implemented for supplied trusted events; legacy raw requests/outcomes, no arrival stamps. Available only after its stated producer record arrives; otherwise null.

1. `auth_failure_count` — authenticated failure reasons, not all 503s. Producer/source: application authentication recorder. Coverage/missing: unknown; status alone cannot attribute missing identity vs provider/response failure. Available only after its stated producer record arrives; otherwise null.

2. `authorization_denial_count` — explicit guard refusal reason. Producer/source: read guard decision recorder. Coverage/missing: unknown; status codes do not encode a trusted authorization reason. Available only after its stated producer record arrives; otherwise null.

3. `unauthorized_attempt_count` — known unauthorized captures among available reads. Producer/source: provider snapshot. Coverage/missing: implemented; old cross_tenant_attempt is not versioned expiry/revocation-aware context. Available only after its stated producer record arrives; otherwise null.

4. `distinct_resource_count` — distinct resource IDs only in known contexts. Producer/source: provider snapshot. Coverage/missing: implemented; old raw paths partial, unknown contexts excluded. Available only after its stated producer record arrives; otherwise null.

5. `repeat_attempt_count` — repeated known attempts within fixed identity/history window. Producer/source: pseudonymous event history. Coverage/missing: unknown; no approved identity-retention/history semantics. Available only after its stated producer record arrives; otherwise null.

6. `request_count_delta` — change between equal complete observed windows. Producer/source: coverage-aware event collector. Coverage/missing: unknown; previous-window completeness not implemented. Available only after its stated producer record arrives; otherwise null.

7. `owner_count` — reads classified owner at capture. Producer/source: provider snapshot. Coverage/missing: implemented; legacy raw principal/owner matches cover some payment reads only. Available only after its stated producer record arrives; otherwise null.

8. `delegated_count` — reads classified delegated at capture. Producer/source: provider snapshot. Coverage/missing: implemented; old static broad owner grants differ from exact expiring grants. Available only after its stated producer record arrives; otherwise null.

9. `unauthorized_count` — reads classified unauthorized at capture. Producer/source: provider snapshot. Coverage/missing: implemented; not generator attack labels. Available only after its stated producer record arrives; otherwise null.

10. `unknown_context_count` — reads with unavailable/invalid authorization category. Producer/source: provider snapshot. Coverage/missing: implemented; missing cannot be relabelled hostile or benign. Available only after its stated producer record arrives; otherwise null.

11. `context_age_max` — maximum cutoff minus request-context capture tick. Producer/source: provider/event clock. Coverage/missing: implemented for supplied events; historical clock/arrival facts absent. Available only after its stated producer record arrives; otherwise null.

12. `revocation_observed_count` — trusted revocation events received before cutoff. Producer/source: authority change stream. Coverage/missing: unknown; snapshot denial does not identify revocation notification availability. Available only after its stated producer record arrives; otherwise null.

13. `active_control_count` — controls active at cutoff from execution ledger. Producer/source: research control host. Coverage/missing: unknown; legacy booleans partial, no new controller. Available only after its stated producer record arrives; otherwise null.

14. `control_remaining_max` — maximum residual duration in clock ticks. Producer/source: research control ledger. Coverage/missing: unknown; legacy max normalized timer not a complete ledger. Available only after its stated producer record arrives; otherwise null.

15. `cooldown_remaining` — remaining independently enforced cooldown ticks. Producer/source: research control ledger. Coverage/missing: unknown; no new cooldown implementation. Available only after its stated producer record arrives; otherwise null.

16. `intervention_count` — cumulative applied adaptive controls this episode. Producer/source: research control ledger. Coverage/missing: unknown; legacy applied actions retained but candidate ledger absent. Available only after its stated producer record arrives; otherwise null.

17. `intervention_budget_remaining` — remaining approved operational units. Producer/source: independent budget gate. Coverage/missing: unknown; budget UNSET, legacy escalation budget is not a generic budget. Available only after its stated producer record arrives; otherwise null.

18. `owner_completed_count` — available owner reads with verified identity-bound 200 responses. Producer/source: trusted response recorder plus provider. Coverage/missing: implemented only under producer response-verification precondition; raw legacy matches partial. Available only after its stated producer record arrives; otherwise null.

19. `delegated_completed_count` — same for currently valid delegation at capture. Producer/source: trusted response recorder plus provider. Coverage/missing: implemented under same precondition; historical exact validity absent. Available only after its stated producer record arrives; otherwise null.

20. `owner_adaptive_denial_count` — known owner reads refused by an actual adaptive control. Producer/source: trusted control outcome recorder. Coverage/missing: implemented for supplied explicit denial events; not inferred from status. Available only after its stated producer record arrives; otherwise null.

21. `delegated_adaptive_denial_count` — same for known valid delegate reads. Producer/source: trusted control outcome recorder. Coverage/missing: implemented for supplied events; historical delegated aggregate available in Phase1, not exact provider snapshot. Available only after its stated producer record arrives; otherwise null.

22. `cumulative_disruption` — episode cumulative separate legitimate adaptive denials. Producer/source: coverage-aware outcome ledger. Coverage/missing: unknown; old aggregate benign_blocked is descriptive generator truth. Available only after its stated producer record arrives; otherwise null.

23. `valid_target_count` — targets passing independent scope/context/control checks now. Producer/source: trusted capability gate. Coverage/missing: unknown; old detector principal list is not source containment authority. Available only after its stated producer record arrives; otherwise null.

24. `missing_context_fraction` — unknown captured contexts / available observed events. Producer/source: provider snapshot aggregator. Coverage/missing: implemented; empty observed window returns null, does not certify complete telemetry. Available only after its stated producer record arrives; otherwise null.

25. `observation_age` — cutoff minus latest visible completion tick. Producer/source: trusted event clock. Coverage/missing: implemented; null with no observed event. Available only after its stated producer record arrives; otherwise null.

26. `adapter_available` — verified collector/provider readiness at cutoff. Producer/source: trusted health recorder. Coverage/missing: unknown; no collector heartbeat; do not infer healthy from a constructed event. Available only after its stated producer record arrives; otherwise null.

27. `control_available` — verified enabled control channel readiness. Producer/source: trusted control host. Coverage/missing: unknown; no new control adapter. Available only after its stated producer record arrives; otherwise null.

28. `supported_action_count` — count of true bits in fixed candidate capability mask. Producer/source: research capability code. Coverage/missing: implemented: one (noop); legacy masks have different semantics. Available only after its stated producer record arrives; otherwise null.

29. `elapsed_ticks` — ticks since episode start in same domain. Producer/source: future episode host. Coverage/missing: unknown; historical step index is not this clock. Available only after its stated producer record arrives; otherwise null.

30. `remaining_ticks` — approved episode horizon minus elapsed ticks. Producer/source: future episode host. Coverage/missing: unknown; future horizon UNSET. Available only after its stated producer record arrives; otherwise null.

31. `observed_disruption_count` — owner plus delegated adaptive denials among observed events. Producer/source: trusted outcome recorder. Coverage/missing: implemented; unknown-context refusals remain separate, no completeness claim. Available only after its stated producer record arrives; otherwise null.

## What this does not prove

Prefix invariance tests add/change future requests, outcomes and permission revisions
and require byte-equivalent earlier values/evidence. Other tests reject late/future
facts and incomparable clocks. These validate a pure builder, not live telemetry
latency/completeness, response verification by a new collector, Markov sufficiency or
customer availability. A future collector needs independently validated cutoff and
arrival records plus complete control history before the proposal is training-ready.

If an owner/delegate snapshot becomes stale or its grant expires before completion,
completion and denial-cost channels for that category become unknown. Historical
request-start classification remains intact; it cannot certify release-time access.
