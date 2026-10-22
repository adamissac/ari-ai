# Live Defense frontend — API contracts needed next

Status: **frontend Phase 1 handoff**. Consumer: `frontend/` Live Defense dashboard
(`feat/live-defense-pilot-ui`). Producer still required: control plane (`backend/`,
`shared/`). This file is a request, not a schema change. **No `shared/` models were
added in the frontend PR.**

Canonical types already in force: `shared/shared/monitoring.py`, `shared/shared/incident.py`,
`shared/shared/rl.py`, generated TS via `frontend/transport`. Negotiation record:
[coordination/CONTRACTS.md](../../coordination/CONTRACTS.md).

## What the UI already consumes (do not fork)

| Method | Path | Shared type | UI use |
|---|---|---|---|
| `GET` | `/projects/{id}` | `Project` | 24/7 defense switch (`settings.monitoring_policy.enabled`) |
| `PATCH` | `/projects/{id}` | `ProjectUpdate` → `Project` | Owner toggle of that flag only |
| `GET` | `/projects/{id}/events` | page of `MonitoringEvent` | Overview event feed. `simulated: true` is labelled. |
| `GET` | `/projects/{id}/reassessments` | page of `ReassessmentRequest` | Overview re-check count |
| `GET` | `/projects/{id}/incidents` | page of `Incident` | Investigation list |
| `GET` | `/incidents/{id}` | `IncidentDetail` | Investigation timeline, linked ids |
| `GET` | `/projects/{id}/defense-recommendations` | labelled page of `DefenseRecommendation` | Overview + explainability. `simulation_derived` is always true. |
| `GET` | `/defense-recommendations/{id}/explanation` | `RLExplanation` | Occlusion contributions |
| `GET` | `/projects/{id}/rl-evaluations` | page of `RLEvaluation` | Imported eval pointers; Lab still reads the committed bundle |

Transport: `frontend/transport/src/client.ts`. Invalid payloads stay unrendered
(`ProtocolError` → “Backend response rejected”).

## Honesty rules the API must keep

1. Telemetry is never invented. `MonitoringEvent.simulated` / `Incident.simulated` stay
   accurate. Ingested live events must be `simulated: false` only when they came through
   authenticated ingest.
2. `DefenseRecommendation.simulation_derived` is `Literal[True]` today. If a future
   live-inference record exists, it needs a **new type** (or an additive flag with a
   different default), not a silent reuse of this DTO as “live confidence”.
3. Q-values on `top_actions` are scores of a stored policy decision. They are not a
   probability that an attack is happening now. Do not add a `confidence_percent` field
   that the UI would be tempted to show as live certainty.
4. No endpoint in this dashboard applies, isolates, rate-limits, or blocks. Those verbs
   must not appear as mutating routes the UI can call. Human incident actions stay on
   `POST /incidents/{id}/actions` (NIST lifecycle only).

## Gaps the Phase 1 UI leaves empty

The dashboard shows these as **“not in the control plane yet”**. Layout-preview fixtures
fill chrome only, behind `?preview=layout` / `/live-defense-pilot`, labelled
“SAMPLE LAYOUT — not live telemetry”.

### 1. Connected applications

Needed to name the system under watch.

Proposed resource (not implemented):

```
ConnectedApplication
  id: app_*
  project_id: prj_*
  name: ShortText
  environment: "sandbox" | "owned_test" | "production"
  ingest_configured: bool          # never return the token
  control_url_configured: bool     # never return the secret
  owner_grants: list[GrantSummary] # kinds allowed, max duration, hourly budget
  created_at: datetime
```

`GET /projects/{id}/applications` → page. 404/empty is preferable to a fake app.

### 2. Component health and topology

Needed for the always-on map (docs/14). Today the live map is omitted because
“healthy” would be a lie.

Proposed:

```
ComponentGraph
  project_id: prj_*
  nodes: list[{ id, label, kind, critical: bool }]
  links: list[{ from, to }]
  observations: list[{
    node_id,
    state: "unknown" | "checking" | "healthy" | "attention",
    last_checked_at: datetime | null,   # null = never checked
    source: "ingest" | "github" | "none",
    simulated: bool
  }]
```

`GET /projects/{id}/defense-graph`

Rules: `healthy` only from a recorded check. `checking` only while a real check is in
progress. Missing observations → `unknown`, never default-healthy. Simulated graphs
must set `simulated: true` on every observation.

### 3. Live-defense incident machine (optional, distinct from NIST `Incident`)

Plan in `docs/LIVE_AUTONOMOUS_DEFENSE_PLAN.md`: DETECTED → TRIAGED → RECOMMENDED →
AUTHORIZED → EXECUTING → VERIFYING → RESOLVED | ROLLED_BACK | ESCALATED.

The current `Incident` type is the human NIST lifecycle (`reported`…`closed`). Do **not**
overload those enums. If the live machine lands, give it its own id prefix and type
(`LiveIncident`) and link to `Incident.id` when a human case is opened.

Until that exists, the Investigation view reads NIST incidents only and sends people to
`/projects/{id}/incidents` for triage/approval/closure.

### 4. Live policy inference (not a confidence feed)

Today explainability loads `DefenseRecommendation.top_actions` and
`GET /defense-recommendations/{id}/explanation`.

If live inference is persisted, the frontend needs:

```
LivePolicyDecision
  id: lpd_*
  project_id: prj_*
  application_id: app_* | null
  checkpoint_sha256: Sha256Hex
  policy_version: ShortText
  action: DefenseActionName
  node: NodeName | null
  q_margin: float
  top_actions: list[ActionScore]
  fallback: "policy" | "rules" | "abstain"
  fallback_reason: ShortText | null
  observation_freshness: "current" | "stale" | "rejected"
  simulation_derived: bool          # true until a live producer exists
  created_at: datetime
```

`GET /projects/{id}/policy-decisions` newest first, cursor page.

Invalid / stale observations must be `fallback: "abstain"` or `"rules"` with a reason —
never a best-effort Q vector from incomplete facts.

### 5. Worker heartbeat

`GET /projects/{id}/defense-health` → `{ worker_seen_at: datetime | null, queue_depth: int | null }`.
Absence → UI stays “unknown”, not “healthy”.

## Failure enums the UI already handles

Existing: `UNAUTHENTICATED`, `FORBIDDEN`, `NOT_FOUND`, `VALIDATION_FAILED`, protocol
mismatch. Please keep using the shared `ErrorResponse`. Do not return 200 with an empty
object for “not implemented”.

For the new resources, prefer:

- `404` + `NOT_FOUND` when the project has no applications / no graph yet
- `501` or `SUBSYSTEM_UNAVAILABLE` if the live-defense worker is not deployed
- `SCHEMA_INVALID` never leaks onto a rendered map

## Authorization

Same as monitoring: project members can read; only owners `PATCH` the 24/7 switch.
New mutating live-defense routes (grants, ingest tokens) must be owner-only and audited.
The frontend Phase 1 PR does not call any of them.

## Out of scope (do not add for this UI)

- Apply / isolate / rate-limit / block adapters callable from the browser
- Changes under `rl-defense/` training, eval, or checkpoints
- Fake backend that echoes layout-preview fixtures as `/api/v1` JSON

## Frontend adapter until agreement

Live mode: existing endpoints only; missing panels are empty with the reason above.
Layout-preview: `frontend/lib/live-defense-preview.ts`, never sent on the wire.

When `shared/` gains the types, regenerate `shared/generated` + `frontend/transport`,
then replace the empty panels. Do not hand-write TS interfaces in `frontend/`.
