# 10 — Continuous monitoring

Status: **specified**. Directory: `monitoring/`. Lifecycle diagram:
[architecture/event-lifecycle](architecture/event-lifecycle.md).

## Purpose

Keep assurance current as the code and its runtime change. Monitoring does
**not** run assessments itself; it decides *what changed, what that affects*, and
*requests* targeted work from the orchestrator under a policy.

## Event sources

| Source | MVP? | Transport | Auth |
|---|---|---|---|
| GitHub `push`, `pull_request` | M | GitHub App webhook → `POST /api/v1/webhooks/github` | HMAC SHA-256 signature (`GITHUB_WEBHOOK_SECRET`), delivery-id dedupe |
| Assessment results (internal) | M | internal event | n/a |
| Runtime logs from the sandboxed demo target | S | file/stdout collector in sandbox → ingestion endpoint | per-project ingest token |
| External runtime telemetry (OpenTelemetry, cloud logs) | L | OTLP receiver | per-project token |
| Dependency advisories (OSV) | L | scheduled poll | public API |

## Normalized event

```
MonitoringEvent {
  id, project_id, repo_id?, source: github|runtime|internal|advisory,
  type: push|pull_request|log_anomaly|assessment_completed|advisory,
  occurred_at, received_at, dedupe_key,
  payload_ref,            # raw payload in artifact store (redacted)
  commit_range?: {base_sha, head_sha},
  entities: [symbol|entry_point|dependency refs]   # filled by correlation
}
```

## Pipeline

1. **Ingest** — verify signature/token, dedupe by `dedupe_key`, store raw
   payload, respond 2xx fast (< 1s) and enqueue `ProcessEventJob`.
2. **Normalize** — map to `MonitoringEvent`.
3. **Correlate** — for code events: index head snapshot (incremental), call
   `affected_by_diff(base, head)` → `ImpactSet` of symbols, expectations, prior
   findings and their regression tests. For runtime events: map routes/log fields
   to entry points.
4. **Decide** — trigger policy (below) produces zero or more
   `ReassessmentRequest`s.
5. **Notify** — UI feed; GitHub commit status / PR comment (S, opt-in).

## Trigger policy (MVP defaults, per project config)

Monitoring starts **OFF**. Owners opt in with the project’s 24/7 defense switch (also available in Defense Lab). Repository automatic assessments also start OFF and require their own explicit opt-in. Migration 0012 resets existing switches once, per the owner’s 2026-10-21 request. Historical Lab replays remain viewable and do not execute live agents.

| Condition | Action |
|---|---|
| Diff touches a symbol with a `verified` finding | Re-run that finding's regression test + Verify check (cheap path) |
| Diff touches a subject of a `confirmed` authorization expectation | Targeted assessment: review + Scout limited to impacted entry points |
| Diff only touches tests/docs | Record, no assessment |
| New dependency or version change | Record; advisory lookup (L) |
| Runtime anomaly score > threshold on an entry point with open findings | Raise priority; request targeted validation; attach RL recommendation if available |

Rate limits: max 1 targeted assessment per repo per 10 minutes; coalesce events
in that window. Budget: monitoring-triggered runs use a lower default cap.

## Runtime anomaly signals (S)

Simple, explainable signals only for MVP: per-route request rate z-score, 4xx/5xx
ratio change, authorization-failure rate change. No ML anomaly detection in MVP;
the RL system consumes these as observations in simulation only.

## Guarantees

- At-least-once processing with idempotent handlers (dedupe key).
- Webhook payloads are untrusted input: size-limited (1 MB), schema-validated,
  never executed, never passed raw to an LLM.
- Monitoring cannot widen scope: requested assessments reuse the project's
  existing active AuthorizedScope; if none, the request is recorded as
  `blocked_no_scope`.

## Project code reviewer settings

When a repository's `automatic_assessments` switch is ON, GitHub pushes and pull
requests use the per-commit reviewer scheduler. Owners configure `review_pushes`,
`review_pull_requests`, `review_draft_prs`, branch globs, author globs, finding
strictness, PR comments and an optional hourly cap in Project Settings. Branch
and author globs are case-insensitive. Empty push include-branches means the
default branch; empty PR include-branches means every base branch. Empty author
includes means everyone; `*[bot]` is excluded by default. Strictness filters only
the PR comment; all findings remain stored.

`GITHUB_AUTO_COMMIT_AUTHORS` is an optional global restriction: empty or `*`
adds no restriction, while a comma-separated list restricts eligible GitHub
authors. The repository opt-in, project monitoring enablement, active approved
scope, project budget, worker/model availability and the global daily spend cap
still apply. The server allows 10 assessments per rolling hour and 50 per rolling
day across triggers; a project may lower, but not raise, its hourly limit.


### Automatic/manual repository mode and Haiku 5.5 (#380)

Each connected repository has a persisted `automatic_assessments` switch, default
OFF. ON enables reviewer scheduling for eligible pushes and pull requests according
to project reviewer settings. OFF prevents unstarted automatic work and exposes manual Run on
selected commits; active runs and history remain intact. GET/PATCH
`/api/v1/repositories/{repo_id}` returns Repository; PATCH requires a project owner
and is audited. Migration 0009 adds the flag; schema 0.15.0 adds RepositoryUpdate
and regenerates JSON/TypeScript. Deploy the backend and frontend together.
For strictly manual operation, keep this switch OFF per repository (or disable
project monitoring); manual Run remains available when the repository switch is OFF.

When configured, `GITHUB_AUTO_COMMIT_AUTHORS` restricts the signed push sender and
GitHub-attributed commit author; empty or `*` imposes no global author restriction.
A shared project quota allows up to 10 assessments per rolling hour and 50 per
rolling day across all triggers; owners may lower the hourly limit per project.
A $50/day spend cap applies globally across triggers and projects. Over-quota automatic
requests are recorded as skipped, not deferred. Full runs use the normal project
budget, clamped to operator caps. Monitoring and approved sandbox scope remain
prerequisites; repair approvals remain required.

Production/staging gateway, Railway startup and frontend quick reads enforce
`claude-haiku-5-5` only, overriding stale production model choices. Errors are
reported instead of substituting another model. Historical recordings retain
the model that produced them. Live production run verification remains outstanding.
