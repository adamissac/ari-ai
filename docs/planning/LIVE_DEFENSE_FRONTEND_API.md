# Live Defense frontend — API contracts (Phase 2)

Status: **Phase 2 implemented** on `feat/live-defense-pilot-phase2`. Consumer:
`frontend/` Live Defense dashboard. Producer: control plane (`backend/`, `shared/`
0.16.0). Phase 1 (PR #390) is unchanged in spirit: live mode still refuses to mix
layout-preview fixtures with records, and no route applies a control.

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
| Stored recommendations + Q ranking | `GET /projects/{id}/defense-recommendations` | Preview ranking | Empty list | Live policy-decision stream (no producer) |
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
2. `DefenseRecommendation.simulation_derived` is `Literal[True]` today. There is still **no live policy-decision producer**; this PR does not add a fake `LivePolicyDecision` feed.
3. Q-values are stored scores, not a probability that an attack is happening now.
4. No endpoint applies, isolates, rate-limits, or blocks. `AnalystReview.accept` sets `executes: false` and `enforcement: "none"`. It is not the NIST two-person incident approval.
5. `DefenseHealth.status` is always `"unknown"`. HTTP 200 is not a healthy verdict.

## Phase 2 resources (implemented)

### Connected applications

`ConnectedApplication` — sandbox or owned_test only. No production. Shadow mode is always true. Secrets never returned.

- `POST /projects/{id}/applications` (owner)
- `GET /projects/{id}/applications`
- `GET /applications/{id}`
- `POST /applications/{id}/ingest-tokens` → `IngestTokenCreated` (token shown once)
- `GET /projects/{id}/ingest-tokens` → page of `IngestTokenView` (owner; no secret)

### Recorded health and topology

- `GET /projects/{id}/defense-health` → `DefenseHealth` (`status` always `unknown`)
- `GET /projects/{id}/defense-graph` → `ComponentGraph` from registered apps and ingest routes. `healthy` is never inferred from HTTP 200. `attention` only when the latest recorded runtime score was anomalous.

### Analyst review

- `POST /defense-recommendations/{id}/reviews` → `AnalystReview` (member+; accept does not enqueue jobs)
- `GET /defense-recommendations/{id}/reviews`
- `GET /projects/{id}/defense-reviews`

## Still missing (do not fake)

- Live-defense incident machine (DETECTED → … → EXECUTING)
- Live policy inference / `LivePolicyDecision` history (no producer)
- Autonomous block / isolate / rate-limit
- Production enforcement grants

## Authorization

Project members can read. Owners register apps, mint/revoke ingest tokens, and toggle 24/7 defense. Members can record analyst reviews. Non-members get 404 (no existence leak). All mutations are audited.

## Out of scope (still)

- Apply / isolate / rate-limit / block adapters callable from the browser
- Changes under `rl-defense/` training, eval, or checkpoints
- Fake backend that echoes layout-preview fixtures as `/api/v1` JSON
