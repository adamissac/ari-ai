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

## Full per-commit rollout (implemented 2026-10-21)

When `GITHUB_AUTO_COMMIT_AUTHORS` is nonempty, GitHub pushes use a separate full
assessment scheduling policy: one durable job per repository/SHA, GitHub-verified
author allowlist, no path-based skipping and no coalescing loss. Railway defaults
to `adamissac`; an explicit comma-separated list or `*` expands the rollout.
This mode uses the normal project assessment budget, clamped by operator limits,
instead of the cheaper monitoring budget above. Monitoring enablement and scope
authorization still apply; scope approval wakes blocked commits. Repair gates
remain human decisions. Empty config retains the legacy impact policy described
above. The new path does not backfill commits received before a repository was
connected, and full execution still depends on configured workers, model access,
repository checkout and an executable authorized sandbox target.
