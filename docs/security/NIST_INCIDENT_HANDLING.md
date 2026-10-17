# Incident handling and NIST SP 800-61 Rev. 3

The incident record supports human incident handling aligned with NIST SP 800-61
Rev. 3 and CSF 2.0. Its states are platform workflow labels, not NIST-prescribed
phases. This feature is not a certification or a claim of complete compliance.

Rev. 3 integrates incident response into cybersecurity risk management. Govern,
Identify and Protect support preparation; Detect, Respond and Recover support
handling adverse events and incidents. Improvement feeds preparation and response
throughout the process. The platform records evidence, decisions, ownership,
escalation, communications, recovery approvals and lessons. It does not replace
an organization's incident response plan, reporting obligations or trained responders.

| Platform state | CSF function and recorded references | Familiar Rev. 2 lifecycle concept |
| --- | --- | --- |
| reported | DE; DE.AE-02 | Detection and analysis |
| triaged | RS; RS.MA-02, RS.MA-03 | Detection and analysis |
| analysis | RS; RS.AN-03 | Detection and analysis |
| containment | RS; RS.MI-01 | Containment, eradication and recovery |
| eradication | RS; RS.MI-02 | Containment, eradication and recovery |
| recovery | RC; RC.RP-01, RC.RP-02, RC.RP-05 | Containment, eradication and recovery |
| closed | RC; RC.RP-06, ID.IM-03 | Post-incident activity |
| rejected | RS; RS.MA-02 | Triage determines the report is not an incident |

Preparation is an organizational activity, not a state that every individual
incident must traverse. The legacy mapping is explanatory and does not turn
Rev. 2 lifecycle labels into Rev. 3 requirements. The current canonical transition
table is in `shared/shared/incident.py`; pure actions are applied by
`standards/standards/incident.py`; its workflow is sequential, with rejection
at reported/triaged. Additional iterative transitions are not implemented.

## API and authorization

All endpoints are under `/api/v1`:

- `GET /projects/{project_id}/incidents`: persisted project reports/incidents.
- `POST /projects/{project_id}/incidents`: owner reports an adverse event.
- `GET /incidents/{incident_id}`: typed `{incident, standards}` detail, including
  persisted finding standards and simulation-derived defensive recommendations.
- `POST /incidents/{incident_id}/actions`: canonical `IncidentAction` operations.
- `POST /incidents/{incident_id}/transition`: alias accepting the same action body.
- `GET /incidents/{incident_id}/events`: finite SSE replay of the durable timeline;
  reconnect with `Last-Event-ID` for subsequent decisions. This is not a continuously
  polling live stream.

Reads require project membership. Writes require owner membership and the session
CSRF token. Linked records must belong to the same project. Owner assignment must
reference an organization member. Every accepted action appends a hash-chained audit
event and an audit-linked timeline entry. Communication actions record a human's
communication summary; they do not send messages.

`IncidentAction.kind` supports `triage`, `assign_owner`, `escalate`, `transition`,
`request_approval`, `decide_approval`, `link`, `record_communication`,
`add_closure_criterion`, `satisfy_closure_criterion`, and `record_lessons_learned`.
Request bodies and allowed values are defined by the shared contract/OpenAPI.

A runtime anomaly crossing the existing threshold on a route with an open validated
security finding creates a **reported adverse event**. It does not declare a confirmed
incident. Repeated related anomalies link to that open record. A project owner must
record a triage decision, category and rationale to confirm or reject it. A vulnerability
finding by itself never becomes an incident. Any simulated linked event or
simulation-derived recommendation preserves the simulated label.

Containment, eradication, recovery and closure require distinct-owner gate approvals.
Requests identify the concrete human action being approved. The requester cannot approve
their own request. These actions record human decisions; the platform never executes
containment, remediation, recovery or other infrastructure actions through this service.
Eradication additionally requires approved remediation and an accepted Verify record
for a linked finding, produced by an independent Verify run in the finding's assessment.

Closure requires an assigned owner, explicit satisfied evidence-linked closure criteria,
lessons learned, and regression evidence pointing to persisted Fortify test artifacts.
Artifact references must match the project and persisted SHA-256. Severity and business
priority remain separate fields. Linked findings remain vulnerabilities, and linked RL
recommendations remain simulation-derived decision support.

## Executed verification

`backend/tests/test_incidents.py` exercises role/CSRF boundaries, human triage,
two-person gates, missing verification rejection, ownership, escalation,
communication recording, closure evidence, SSE resume and audit-chain integrity.
Its complete lifecycle uses the offline reference orchestrator through the real
backend, persisted remediation approval, independent Verify and Fortify artifact.
`backend/tests/test_runtime_ingest.py` verifies anomaly correlation and simulation
labeling. These are deterministic integration tests, not evidence of production
incident detection or comprehensive NIST compliance.

Source: [NIST SP 800-61 Rev. 3](https://csrc.nist.gov/pubs/sp/800/61/r3/final).

The backend reuses `open_incident` and `apply_action` from the standards package.
It adds database checks that pure rules cannot perform: project ownership of links,
organization membership for assignment, persisted artifact hashes, Fortify regression
relationships, accepted Verify provenance and the corresponding remediation approval.
Only those verified identifiers are passed as accepted verification evidence to the
canonical lifecycle rules. The API currently requires owner membership for all writes,
a stricter policy than the pure rules' member allowance for some actions.

Migration revision `0005_incidents` deliberately differs from intelligence-memory PR #39’s `0005`. The runner upgrades all current Alembic heads, allowing independent additive branches to coexist. A real PostgreSQL scratch-database test upgrades both heads, downgrades to base, and upgrades again. Disposable databases from earlier unpublished iterations should be recreated; no production upgrade from an earlier incident prototype is claimed.
