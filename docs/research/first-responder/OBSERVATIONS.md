# Partial observability and decision-time representation

Proposed formulation: a finite-budget POMDP with separately constrained costs.
Latent state includes true incident cause, relevant vulnerabilities, agent information
yet to be obtained and future analyst availability. History contains only records
available before each decision. Requesting an agent may change later information,
remaining budget and elapsed time; notification may change analyst response. These
transitions and delayed effects are plausible, not measured or implemented dynamics.
A summary vector is not proven Markov. A future recurrent/history policy would need
its own registered representation and leakage checks; DDQN is not assumed adequate.

## Implemented fixture observation 0.1-proposal

Eleven nonnegative raw values, eleven known bits and twelve feasibility bits are
separate immutable tuples. Concatenating would yield 34 channels, but no trained
normalization, production encoding or training vector is specified. Unknown numeric
slots contain zero only alongside known=false; zero cannot be read as a measured fact.
IDs, evidence hashes, version, cutoff and snapshot are audit metadata, not numeric
policy features. Severity is source-defined, not an agent confidence/reward score.

- incident_age_seconds: host incident clock; seconds from an authenticated event origin.
- suspicious_count: authenticated telemetry aggregate with declared window and completeness.
- severity_indicator: versioned trusted triage indicator, distinct from ground truth.
- verified_findings: independently verified, commit-matched findings; unknown without deployment binding.
- pending_tasks: durable job ledger, not inferred from absence of result receipts.
- remaining_budget_usd: host charge/reservation ledger, not guessed from Usage defaults.
- active_controls: enforcement ledger, not recommendations or analyst acceptances.
- analyst_acknowledged: observed acknowledgement only; no inference of availability/correctness.
- completed_agent_runs: visible successful terminal receipt count in the bounded input set.
- failed_agent_runs: visible failed/cancelled terminal receipt count in that set.
- terminal_run_cost_usd: sum for that set only when every terminal receipt has attested USD.

The last three are not complete incident totals: no producer completeness watermark
exists here. Empty sets remain unknown; partial charge coverage remains unknown.
Future cumulative aggregates require authoritative reconciliation, not truncation of
bounded receipt history. No useful-evidence label is derived from result prose.
Receipt field semantics are fixture assumptions awaiting actual producer agreement.

Incident type, route/service identity, uncertainty reasons, category-specific findings,
remaining control duration, escalation state, elapsed agent time and monitoring mode
remain proposed future fields. Main contains relevant typed records, but no proven
first-responder decision-time producer binds them. Do not encode unavailable features
as known zero or expand the model silently.

## Cutoff and provenance

Every fact/capability/scope/result has tenant/repo/assessment/incident identity,
clock/journal identity, observation time, availability time, sequence, expiry and
nonempty canonical EvidenceRefs. Visibility requires observed_at AND available_at
strictly before cutoff time AND sequence strictly before cutoff sequence. Future
records cannot backfill prior observations. Incomparable clocks and visible foreign
contexts fail. Latest visible revision wins before TTL filtering: expiry/revocation
cannot revive an older permission. Equal-sequence conflicting revisions fail.

SnapshotRef alone proves indexing identity, not deployment. A fresh trusted binding
receipt is additionally required; missing deployed version masks requests and makes
verified findings unknown. Source availability is not source truth: signatures,
artifact existence, authenticated ingestion, deployment verification and role-output
validation remain producer/host obligations. The pure adapter does not implement them.
Known bits mean supplied, fresh and context-matched in a fixture, not independently
verified real-world truth. Visible stale receipts remain in audit provenance.

Result receipts bind canonical AgentRun and AgentStepResult IDs, role, assessment,
status, Usage and completion time; successful runs require output artifact identity.
Raw result prose, hidden attack labels, future outcomes, future analyst responses,
post-hoc adjudication and counterfactual damage never enter numeric observations.
A future independent outcome evaluator may see sealed labels only after decisions;
it must not write those labels back into policy input history.

Decision binds the observation digest, behavior policy identity and later issue
sequence/time. Behavior probability stays null unless actually known. executed=false
and training_eligible=false are mandatory. Fixture acceptance proves local boundary
behavior only; no dispatch or training eligibility follows from it.
