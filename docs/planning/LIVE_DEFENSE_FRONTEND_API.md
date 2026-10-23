# Live Defense frontend — API contracts (Phase 3)

Status: **Phase 5 shadow-pilot readiness** on `feat/live-defense-phase5-pilot-readiness`
(extends Phase 2/3 on `origin/main`). Phase 4 enforcement (PR #393) is **not**
included.
Consumer: `frontend/` Live Defense dashboard. Producer: control plane (`backend/`,
`shared/` 0.17.0). Phase 1 (PR #390) and Phase 2 (PR #391) are extended, not rebuilt:
live mode still refuses to mix layout-preview fixtures with records, and no route
applies a control.

Canonical types: `shared/shared/monitoring.py`, `shared/shared/incident.py`,
`shared/shared/rl.py`, `shared/shared/live_defense.py`, generated TS via
`frontend/transport`.

## Integration audit (Phase 1 on main `53bf03c`, extended here)

| Surface | Real backend | Sample layout (`?preview=layout` / `/live-defense-pilot`) | Empty / missing evidence | Unimplemented |
|---|---|---|---|---|
| Project + 24/7 switch | `GET/PATCH /projects/{id}` | Not used | Switch off is an explicit recorded setting | — |
| Events | `GET /projects/{id}/events` | Preview fixtures, labelled SAMPLE LAYOUT | Empty feed copy; no invented events | — |
| Reassessments | `GET /projects/{id}/reassessments` | Not shown as live counts | Zero is zero | — |
| NIST incidents + timeline | `GET /projects/{id}/incidents`, `GET /incidents/{id}` | Preview incidents | Empty list; unknown correlation when no linked ids | Live DETECTED→EXECUTING machine |
| Stored recommendations + Q ranking | `GET /projects/{id}/defense-recommendations` | Preview ranking | Empty list | — |
| Shadow `LivePolicyDecision` | `GET /projects/{id}/live-policy-decisions` | Not mixed with live | Empty list | Q-values when inference did not run (never synthesized) |
| Occlusion explanation | `GET /defense-recommendations/{id}/explanation` | Preview contributions | Button loads stored explanation; missing fields = unavailable | — |
| RL evaluations | `GET /projects/{id}/rl-evaluations` | Not used | Empty; Lab reads committed bundle | — |
| Staging apps | `GET/POST /projects/{id}/applications` | Sample chrome only | Empty onboarding | Production environment (rejected) |
| Ingest tokens | mint shown once; `GET` metadata never includes secret | Not minted | last-used unavailable until ingest | Re-showing the secret |
| Defense health | `GET /projects/{id}/defense-health` | Not used | `status` always `unknown` | Inferring healthy from HTTP 200 |
| Recorded topology | `GET /projects/{id}/defense-graph` | Illustrative map, labelled sample | List of recorded apps/routes; no decorative chart | Simulator node map as customer topology |
| Analyst review | `POST/GET .../reviews` | Not used | History empty | Accept executing a control |

Unknown correlations (event not on any incident, incident with no recommendation ids) are labelled **unknown**, never invented.

## Honesty rules the API must keep

1. Telemetry is never invented. `MonitoringEvent.simulated` / `Incident.simulated` stay accurate.
2. `DefenseRecommendation.simulation_derived` is `Literal[True]`. Genuine shadow rows are `LivePolicyDecision` (`enforcement: "NOT_EXECUTED"`). Q-values on a live decision are null unless frozen v6 inference actually ran.
3. Q-values are stored scores, not a probability that an attack is happening now.
4. No endpoint applies, isolates, rate-limits, or blocks. `AnalystReview.accept` sets `executes: false` and `enforcement: "none"`. It is not the NIST two-person incident approval and is not converted into an RL label.
5. `DefenseHealth.status` is always `"unknown"`. HTTP 200 is not a healthy verdict.

## Phase 2 resources (implemented)

### Connected applications

`ConnectedApplication` — sandbox or owned_test only. No production. Shadow mode is always true. Secrets never returned.

- `POST /projects/{id}/applications` (owner)
- `GET /projects/{id}/applications`
- `GET /applications/{id}`
- `POST /applications/{id}/ingest-tokens` → `IngestTokenCreated` (token shown once)
- `POST /applications/{id}/ingest-tokens/rotate` → `IngestTokenRotated` (new secret shown once; prior ids listed)
- `POST /applications/{id}/disconnect` → `ConnectedApplication` (`verification=disconnected`)
- `POST /applications/{id}/shadow-verify` → `ConnectedApplication` from recorded ingest (not a healthy verdict)
- `GET /projects/{id}/ingest-tokens` → page of `IngestTokenView` (owner; no secret)
- `GET /projects/{id}/pilot-report` → `PilotReport` (HTTP 200 is not attack success; never claims shadow prevented breaches)

### Recorded health and topology

- `GET /projects/{id}/defense-health` → `DefenseHealth` (`status` always `unknown`)
- `GET /projects/{id}/defense-graph` → `ComponentGraph` from registered apps and ingest routes. `healthy` is never inferred from HTTP 200. `attention` only when the latest recorded runtime score was anomalous.

### Analyst review

- `POST /defense-recommendations/{id}/reviews` → `AnalystReview` (member+; accept does not enqueue jobs)
- `GET /defense-recommendations/{id}/reviews`
- `GET /projects/{id}/defense-reviews`

## Phase 3 resources (implemented)

- `GET /projects/{id}/live-policy-decisions` — cursor-paginated shadow decisions
- `GET /live-policy-decisions/{id}`
- `POST/GET /live-policy-decisions/{id}/reviews` — accept does not execute
- Authenticated ingest source `owned_staging` (application-bound token)
- Deterministic rules in `monitoring/detect.py`; frozen v6 only when serving assumptions hold

## Still missing (do not fake)

- Live-defense incident machine (DETECTED → … → EXECUTING)
- Autonomous block / isolate / rate-limit
- Production enforcement grants

## Authorization

Project members can read. Owners register apps, mint/revoke ingest tokens, and toggle 24/7 defense. Members can record analyst reviews. Non-members get 404 (no existence leak). All mutations are audited.

## Out of scope (still)

- Apply / isolate / rate-limit / block adapters callable from the browser
- Changes under `rl-defense/` training, eval, or checkpoints
- Fake backend that echoes layout-preview fixtures as `/api/v1` JSON
