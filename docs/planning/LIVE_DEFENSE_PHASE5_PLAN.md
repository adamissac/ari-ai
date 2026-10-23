# Live Defense Phase 5 plan — customer shadow-pilot readiness

Status: **implemented** on `feat/live-defense-phase5-pilot-readiness` from
`origin/main` (`09e8cab`). This is **not** Phase 4 owned-test enforcement and
does **not** include executable controls from PR #393.

Codex owns RL research. This work does not train, promote, or edit v6 weights,
datasets, or the promotion registry.

## Goal

A customer **shadow-pilot** can register an authorized staging app, issue and
rotate ingest credentials, send authenticated telemetry, see honest unknown
health, investigate recorded events, and export a report. Nothing here applies,
isolates, rate-limits, or blocks. Analyst accept still does not execute.

## What this slice adds on top of Phase 2/3

| Capability | How |
|---|---|
| Staging registration | Existing `POST /projects/{id}/applications` (sandbox / owned_test) |
| Credential issue / rotate / revoke | Issue + `POST .../ingest-tokens/rotate` + existing revoke |
| Ingest auth / schema / dedupe / tenant / provenance | Existing `/ingest/runtime/{project_id}` |
| Explicit shadow-mode | `ConnectedApplication.shadow_mode` is always true |
| Verification | `POST /applications/{id}/shadow-verify` recomputes from recorded ingest; not a healthy verdict |
| Disconnect | `POST /applications/{id}/disconnect` revokes tokens; further ingest 401 |
| Worker / telemetry / policy health | `DefenseHealth` fields stay `unknown` without a health-check producer |
| Alerts | Existing audit log + `advisory` monitoring events |
| Onboarding UI | Staging apps: rotate, disconnect, verify, export |
| Investigation trail | NIST incidents + audit actions in the pilot report |
| Exportable pilot report | `GET /projects/{id}/pilot-report` |

## Explicit non-goals

- Customer production enforcement
- Autonomous RL
- Browser-callable block / isolate / rate-limit
- Merging or depending on PR #393 executable controls
