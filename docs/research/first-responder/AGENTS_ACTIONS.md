# Actual agent capabilities and proposed actions

This is a source audit, not an execution benchmark. Exact fields, tool allowlists,
versions and hashes are in [SOURCE_INVENTORY.json](SOURCE_INVENTORY.json). Runtime
roles are distinct typed implementations under security-agents/security_agents/agents;
the deterministic backend host owns DAG prerequisites, budgets, cancellation and
scope checks. Read-only does not mean cost-free or safe to run on arbitrary inputs.

## Class A — candidate read-only investigation requests

Scout reads retrieved code, graph, expectations, finding history and static analysis.
It requires an assessment, indexed snapshot/commit, entry points and bounded scope.
Its output is hypotheses and coverage, not proof of an attack. Source caps: 300 seconds,
40 tool calls, 16 turns, 16,000 output tokens.

Trace reads code/graph/expectations/history after a confirmed Probe validation result;
it needs finding/validation IDs and observations. Output is trace/preconditions/impact
analysis, not new dynamic validation. Caps: 180 seconds, 25 calls, 12 turns, 16,000 tokens.

Diagnose reads code/graph/expectations/history/static analysis with finding and validation
context to propose root cause and remediation strategy. It does not repair. Caps:
180 seconds, 25 calls, 12 turns, 16,000 tokens.

Fortify reads the same static context after verification, requiring verification_result_id.
Output is hardening/regression suggestions, not executed tests. Caps: 180 seconds,
20 calls, 10 turns, 16,000 tokens. Its required upstream verification does not authorize
this research policy to invoke Verify.

All four have network='none', sandbox_profile='none', write_access='none' in their
SPEC. Host tool registry must independently preserve those properties and approved
retrieved-context boundaries. Expected information gain is a hypothesis to measure;
USD and latency are unknown until attested. Their analysis cannot retract disclosure
or consumed budget: cancellation stops future work, not already incurred costs.
Timeout/failure must produce explicit terminal status and retained partial artifacts;
no automatic retry is assumed by research.

## Excluded from the initial proposal action set

Probe executes registered templates in a scoped check-runner sandbox with target-only
network and output-directory writes (180 seconds / 12 calls / 10 turns). Patch writes
an isolated worktree and executes tests under human remediation approval, network none
(480 seconds / 50 calls / 30 turns). Verify applies a candidate in an independent fresh
sandbox and executes checks/tests, target-only network (480 seconds / 20 calls /14 turns).
Verify's read-only patch access does not make its tools passive. These workflows
require separate scope, approvals, sandbox and independence guarantees. They remain
available through existing product workflows, not through this candidate policy.
No generic gather-evidence, arbitrary tool call or open/confirm-incident action is added.

## Fixed proposal ordering (internal research version 0.1)

Indices 0–11: abstain; continue_monitoring; request_scout; request_trace;
request_diagnose; request_fortify; request_analyst_notification; request_escalation;
recommend_route_limit; recommend_source_limit; request_containment_approval;
request_stop_investigation. Enum order is internal, not a production action ABI.

Abstain and monitor are local no-dispatch proposals. They cannot disable independent
host emergency stops, expiry, budget enforcement or required escalation rules.
Class A comprises indices 2–5 and requires actual role-input readiness, current scope,
verified deployment binding, host eligibility and remaining budget. Existing DAG
prerequisites are not relaxed. Each mask bit is a proposal filter, never authority.

Class B comprises notification/escalation requests. Require trusted allowlisted
recipient/destination, host rate/dedup/cooldown checks and budget. Expected benefit
is acknowledged, actionable handoff, not sending more alerts. Sending consumes
analyst attention and cannot be undone. Delivery, acknowledgement and correctness
are distinct records. Timeout is unknown delivery until reconciled; no silent retry.
Stop-investigation is a host workflow request: it cannot cancel mandatory independent
verification or erase an incident. Research conservatively gates it like other
requests; mandatory host cancellation always remains available outside this mask.

Class C comprises route/source recommendations and containment-approval requests.
They require scoped resources, supported host capabilities, current evidence and
approved budgets to be proposed. They never execute controls or create ControlGrants.
Recommendation lifetime, proposed duration and expiration need the future contract;
no default disruptive duration is invented. Any later execution requires separate
human/customer authorization and deterministic target/TTL/budget checks. Only actual
execution may have traffic side effects; reversal/expiry and disruption must then be
measured by the enforcement host. A recommendation has no measured containment benefit.

All dispatches, if later integrated, must recheck scope, identity, freshness, pending
work, budgets and cancellation at use time. Unsupported, ambiguous or missing context
masks requests; invalid proposed actions fail visibly rather than becoming no-ops.
Host timeouts and terminal accounting are independent of policy preferences.
