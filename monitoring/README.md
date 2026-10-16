# monitoring/

> **What exists: nothing yet (Phase 0).** Spec: [docs/10](../docs/10_CONTINUOUS_MONITORING.md),
> lifecycle: [docs/architecture/event-lifecycle](../docs/architecture/event-lifecycle.md).

## Purpose
Keep assurance current: ingest repository and runtime events, determine what
they affect, and request targeted re-assessment under a policy.

## Responsibilities
- GitHub webhook verification (HMAC), dedupe, raw payload storage (redacted).
- Normalization to `MonitoringEvent`; correlation to `ImpactSet` via
  code-intelligence.
- Trigger policy, coalescing and rate limits → `ReassessmentRequest`.
- Runtime log signals from the sandboxed demo target (stretch).
- Feed events and context to RL recommendations.

**Must not:** run assessments itself, widen scope, pass raw payloads to an LLM,
execute payload content.

## Interfaces
| Interface | Notes |
|---|---|
| `monitoring.webhooks.handle_github(headers, body)` | Mounted by backend at `/api/v1/webhooks/github` |
| `monitoring.ingest.handle_runtime(project_id, token, events)` | `/api/v1/ingest/runtime/{project_id}` |
| `ProcessEventJob` handler | worker |
| Emits `ReassessmentRequest` | backend orchestration service |

## Dependencies
`shared/`; `backend` persistence + queue; `code_intelligence.api.affected_by_diff`;
GitHub App ([ADR-0009](../docs/decisions/0009-github-app-integration.md)).

## Planned layout
```
monitoring/
  monitoring/ webhooks/ ingest/ normalize/ correlate/ policy/ signals/
  tests/ (recorded webhook fixtures)
```

## First tasks
MON-001 → MON-002 → MON-003; MON-004 (stretch).

## Commands
None yet.
