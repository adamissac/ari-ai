# monitoring/

Pure, deterministic monitoring logic (no I/O): GitHub payload normalization, impact
correlation and the reassessment trigger policy ([docs/10](../docs/10_CONTINUOUS_MONITORING.md)).
Persistence, signature verification, jobs and assessment creation live in `backend/`
(`backend/api/webhooks.py`, `backend/pipeline.py`). Owner: **Srihith**.

## What exists

* `monitoring.normalize` — `push` / `pull_request` → `GitHubChange` (validated SHAs, capped
  strings, path traversal rejected, truncated pushes marked incomplete); everything else
  → `Ignored(reason)`.
* `monitoring.impact` — `ImpactProvider` protocol for code-intelligence
  `affected_by_diff`; honest `path_only` fallback; rejects impact for a different SHA.
* `monitoring.policy.decide` — record-only (tests/docs), `blocked_no_scope`, coalescing
  (open or recent monitoring assessment), `regression_only` for verified-finding paths,
  `targeted`, `full` when the path list is incomplete.

## Honesty notes

"24/7" requires the worker deployed and running; locally it runs only while
`make worker` / Compose is up. Locally signed deliveries are simulated events.
Runtime telemetry ingestion (`/ingest/runtime`) is not implemented.

## Commands

`uv run pytest monitoring/tests`
