# Event lifecycle

Status: **specified**. Product spec: [10](../10_CONTINUOUS_MONITORING.md).

## Push event → re-assessment

```mermaid
sequenceDiagram
  participant GH as GitHub
  participant API as API /webhooks/github
  participant Q as Queue
  participant W as Worker (monitoring)
  participant CI as Code intelligence
  participant O as Orchestrator
  GH->>API: push (signed)
  API->>API: verify HMAC, dedupe delivery id, store raw (redacted)
  API-->>GH: 202
  API->>Q: ProcessEventJob(evt)
  Q->>W: normalize → MonitoringEvent
  W->>CI: index head snapshot (incremental from base)
  W->>CI: affected_by_diff(base, head) → ImpactSet
  W->>W: trigger policy
  alt verified finding touched
    W->>O: ReassessmentRequest(scope=targeted, regression tests)
  else confirmed authz expectation touched
    W->>O: ReassessmentRequest(targeted assessment)
  else nothing relevant
    W->>W: record only
  end
  O-->>API: SSE / feed update
```

## Event states

`received → normalized → correlated → decided → (requested | recorded | blocked_no_scope | coalesced) → done`,
or `failed` with error code. Each state change is stored on the event row.

## Coalescing

Events for the same repo within a 10-minute window merge into one
ReassessmentRequest using the newest head SHA and the union of impacts.

## Runtime events (S)

Collector inside the target sandbox writes JSON lines → worker tails `/out` →
computes per-route signals → `MonitoringEvent(type=log_anomaly)` if a threshold
is crossed → same decision step. Signals can also be exported as observation
sequences for RL offline evaluation.
