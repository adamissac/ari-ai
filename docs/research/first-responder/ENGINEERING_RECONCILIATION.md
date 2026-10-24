# Newly available engineering candidate — read-only reconciliation

During final PR review, a fetch discovered engineering PR #439, branch
`cursor/live-defense-first-responder-0044`, pinned here to
1227e0d2b77c924c211339ae7dee57daae979ffc. It explains the requested
feat/live-defense-first-responder name was replaced by its cloud branch convention.
This is a candidate reference, not owner confirmation of an agreed integration.
It is open and explicitly requires human security review. This research PR neither
merges nor executes it. The initial source inventory remains a historical audit at
711189; its not-supplied Grok status describes that earlier audit, not this discovery.

Source reviewed (using git show, no imports/execution): shared/shared/live_defense.py;
backend/backend/live_defense/orchestrator.py; first_responder.py; and the Phase 7A
coordination message. This is a contract comparison, not complete security review
or verification of the engineering PR's reported tests.

## Available proposal fields and remaining gaps

Decision-time context: FirstResponderDecision proposes project/application/optional
incident identity, created_at, trigger event IDs, mode, correlation and selected/blocked
agents. RuntimeCodeCorrelation and owner-attested DeployCommitMapping propose deployed
commit association. These do not yet provide this research proposal's complete
availability journal/cutoff sequence/clock, freshness watermarks, immutable retrieved
input snapshot or feature-level EvidenceRefs. Owner attestation is an explicit trust
assumption, not independently verified deployment proof.

Capabilities/masks: AgentCapabilityRegistry derives seven roles from real AgentSpecs
and includes tools, network and write access. Selected/blocked agents record some
eligibility reasons; they are not a complete versioned predecision feasible set for
our twelve proposal actions, nor proof of role-specific input readiness. Production
permission checks remain separate from any research mask.

Requests/outcomes: FirstResponderInvocation proposes decision/job/agent/scope identity,
status and provider_mode. At the pinned candidate, run_first_responder_agent_step
records provider_mode=none and completed_unverified/skips; it does not establish an
executed live Claude agent loop or a canonical AgentRun/AgentStepResult evidence link.
Do not map completed_unverified to our successful-agent receipt or useful evidence.
Our adapter is not connected to these records.

Costs/latency: proposed budget_usd_remaining/deadline/retry/loop fields and creation
times are useful context. Invocation DTOs lack reconciled charged Usage, full
queue/start/completion/availability times and charge-completeness attestation.
Configured remaining budget is not measured treatment cost or end-to-end latency.

Escalation/recommendations: AnalystHandoff distinguishes queued/delivered states and
provider confirmation. FirstResponderDecision makes recommended_is_not_executed and
executed=false explicit. Those align with the research boundary; delivered is not
analyst acknowledgement, correct escalation or harm reduction. Current confirmation
records require independent executable evidence, not LLM prose.

Decision/outcome provenance: orchestrator version, triggers, simulated flag and later
human outcome_label are proposed. predicted_probability stays null, correctly avoiding
invented propensities. Generic human labels still need independent rubric/provenance;
no outcome label may enter earlier observations. Complete cost/source/mask journals
and counterfactual support remain absent from this candidate contract.

## Decision

CONDITIONAL GO / no learning yet is unchanged. The engineering candidate advances
the baseline specification, not proof of measured sequential benefit or training
readiness. Reconcile after owner reference confirmation and contract/security review;
any canonical additions belong to the shared owner. No schema, API, worker, incident,
adapter integration, collection or enforcement changes are made here. PR #439's
explicit human security-review requirement remains in force.
