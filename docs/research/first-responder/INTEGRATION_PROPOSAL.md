# First-responder research contract0.1 — PROPOSED, NOT IN FORCE

Grok owns telemetry, incidents, agent invocation, deterministic orchestration,
escalation, workers, dashboard and integration. Research owns observation/proposal
semantics, evaluation and readiness. Owner confirms proposed engineering branch
`feat/live-defense-first-responder` may not yet be pushed; exact reference will be
provided later. A final fetch discovered candidate engineering PR #439; see
[the pinned reconciliation](ENGINEERING_RECONCILIATION.md). It is not an agreed
integration or completed security review. This does not block fixture-only work. No unfinished
engineering code is treated as a producer, and no shared production schema changes
or worker hooks are made here. Agreement and canonical shared-owner review precede
any integration. Existing SnapshotRef, EvidenceRef, AgentRun, AgentStepResult and
AuthorizedScope models are reused, never redefined.

## Minimum producer/consumer proposal

All fields below are proposals until Grok supplies the actual implementation.
Current `rl_defense.research.first_responder` models are internal fixture inputs,
not network DTOs, shared replacements or authority-bearing tokens.

| Area | Required fields / semantics | Trusted producer |
|---|---|---|
| Decision-time observations | schema_version, project/repo/assessment/incident IDs, deployed app identity, verified deployment→SnapshotRef binding, feature names/units/known bits, source revision | Grok runtime/capture adapter using authenticated ingest and authoritative deployment binding; never client ownership/commit claims |
| Availability | observed_at, available_at, available_seq, clock_id/journal epoch, decision cutoff time/sequence, valid_until, completeness/watermark and collection mode | Durable host journal; cross-agent local counters cannot be compared without reconciliation |
| Capabilities/masks | action/target identity, capability version, required role-input ArtifactRef, pending/dedup state, host eligibility reason, tool budget and freshness, known/unknown flags | Deterministic host capability service; proposed mask is not execution authorization |
| Agent requests/outcomes | request/run/decision IDs, dependency DAG/input snapshot+hash, canonical AgentRun and AgentStepResult, role-output schema version/artifact, provider_mode/model/prompt/toolchain versions, started/completed/available timestamps, terminal status/error | Existing agent execution/host, through reviewed APIs; role outputs validated before use |
| Cost/latency | charged tokens/USD/tool calls, sandbox seconds, queue/provider/run durations separately, charge completeness, reservations/remaining budgets | Trusted charge/job ledger; Usage defaults do not prove measured zero, sandbox_seconds is not end-to-end latency |
| Escalation/recommendations | decision/request/recommendation IDs, approved destination, dedup/cooldown, reason/evidence, requested/queued/delivered/acknowledged states; containment type/target/duration and approval state separate | Grok notification/approval host; analyst accept is not executed containment or ground truth |
| Provenance/learning | event/source artifact hashes, exact SnapshotRef, producing component version, behavior policy/config version, predecision feasible set, selected proposal, probability if actually known, result/outcome availability and independent adjudicator | Host and independent evaluator; unknown probability stays null, no retrospective observation backfill |

The current fixture adapter enforces strict time AND sequence cutoffs, context/clock
and snapshot binding, newest-visible revisions (expired latest state does not revive
older permission), evidence references, and scope expiry/revocation checks. It does
not validate signatures, fetch artifacts, prove deployment identity or validate
role-specific LLM outputs itself. Those are producer/host responsibilities and must
be demonstrated, not inferred from a fixture boolean. Result receipts pair canonical
run/result role, ID, assessment, status, usage and completion time; output prose is
never a measured usefulness signal.

## Security boundaries

`integration_agreed=false` by default. Even hypothetical agreed fixture capabilities
only enable *proposal masks*. This module has no dispatch, notification, database,
network, training, permission-grant or control-execution function. All Decision rows
are executed=false and training_eligible=false. A positive fixture mask cannot
create a real scope, grant, incident transition, approval, agent run or control.
Future host authorization must recheck current scope/identity/budget/TTL/dedup
immediately before every tool/request, independently of model output and cached
research masks. Global cancellation, expiry, budget stops and emergency stop remain
host actions even if a learned policy proposes monitor or abstain.

Customer read authorization stays with the application's trusted provider. Runtime
ControlGrant permission is a different service. A request for containment approval
requires the independent host workflow; it cannot mint its own grant or transition
an Incident into an approval-gated state. Existing person-bound incident triage
semantics must be reconciled explicitly if Grok proposes autonomous incident opening.
No production action indices, migrations, APIs or generated types are changed.

## Payload examples and reconciliation

Runnable synthetic examples are in `rl-defense/tests/test_first_responder.py`:
`enabled()` plus `observe()` is an explicitly hypothetical, agreed fixture; default
`frame()` enables only local monitor/abstain proposals. Invalid examples include
executed=true, training_eligible=true, action=execute_containment, grant=self-approved,
foreign tenant/incident/SHA/clock, late receipts, stale/expired scopes and mismatched
AgentRun/AgentStepResult. Actual payload approval must occur in shared/ after Grok
reviews these fields; fixture passing is not contract-owner acceptance.

Reconcile when an exact branch/PR is supplied: compare actual fields and availability
clock semantics, record missing capability/outcome producers, negotiate minimal
additive shared types with owner review/codegen/consumer tests, and only then add a
research capture adapter. No production integration is authorized by this proposal.
