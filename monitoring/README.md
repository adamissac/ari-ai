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
`monitoring.collector` is the one module here that does I/O: an ASGI middleware that
runs inside a monitored app and posts per-route counters to `/ingest/runtime`. It has
not been installed on a real application yet. `monitoring.controls` is its partner:
the signed control endpoint Ari calls on a production app (ADR-0027).

## Live Defense for an app in any language

`monitoring.proxy` is a sidecar reverse proxy. Put it between your load balancer and your
app; the app's language and framework do not matter. It forwards every request unchanged and
adds Ari's telemetry (`monitoring.collector`) and Ari's signed control endpoint
(`monitoring.controls`, at `/live-defense/control`).

```
uv sync --extra proxy
ARI_UPSTREAM=http://127.0.0.1:3000 \
ARI_CONTROL_SECRET=<shown once when you registered the channel> \
ARI_API_BASE=https://<ari api> ARI_PROJECT_ID=prj_... ARI_INGEST_TOKEN=<app ingest token> \
ARI_ROUTES='/payments/{id},/users/{id}/orders' \
python -m monitoring.proxy --listen 0.0.0.0:8080 --trust-forwarded-for
```

- `ARI_ROUTES` (or `--routes FILE`) lists your route templates. Telemetry reports a request
  under its template; anything unlisted is counted as `/__unmatched__`. Raw paths, queries,
  headers and bodies are never sent.
- `--trust-forwarded-for` makes source blocks use the last `X-Forwarded-For` entry, the
  address your load balancer saw. Leave it off when nothing sits in front of the proxy.
- Register `https://<your public host>/live-defense/control` in Ari, then press Check endpoint.
- Python ASGI apps can skip the proxy and add `AriCollector` and `AriControls` as middleware.

Limits: controls live in the proxy's memory, so run **one** proxy instance (several replicas
would each hold different controls); a restart drops active controls, which Ari then reports
as not verified or removed. WebSockets are not proxied. Serverless platforms with no
long-running process in front of the app are not covered.

## Commands

`uv run pytest monitoring/tests`
