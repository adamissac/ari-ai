# Live autonomous defense: audit and plan

Status: **Phase 4 owned-test enforcement is implemented** on
`feat/live-defense-phase4-controlled-enforcement` (plan:
[LIVE_DEFENSE_PHASE4_PLAN](planning/LIVE_DEFENSE_PHASE4_PLAN.md), ADR-0019).
Phase 1–3 remain: shadow dashboard, authenticated ingest, `LivePolicyDecision`
NOT EXECUTED, analyst accept does not execute. Phase 4 adds a **separate**
`LiveControl` lifecycle and a deterministic authorization gate that can apply
four minimal actions only on a registered loopback owned-test app. Production
grants, isolation, autonomous (no-human) enforcement, and customer traffic
control are still **not** implemented. Do not treat the original sections 4–7
below as the Phase 4 code path — they mixed NIST incident statuses with
execution; Phase 4 does not.

## 1. What already exists (audited on main `8943622`)

| Area | Exists | Reusable as is | Gap for live defense |
|---|---|---|---|
| Ingest auth | `ingest_tokens` (per project, SHA-256 at rest, revocable), Bearer auth in `backend/api/runtime.py` | Yes | Only aggregated route counters, no per-event telemetry |
| Runtime scoring | `monitoring.runtime.score_window` (z-score, error and auth-failure deltas) | Yes, as a signal | Heuristic over counters; no source attribution |
| Job queue | `backend/jobs.py`: SKIP LOCKED claims, leases, heartbeats, backoff, dedupe keys, dead letters | Yes | No worker liveness record for health checks |
| Incidents | `backend/incidents.py` + `standards.incident`: NIST SP 800-61r3 lifecycle, human actions only | Yes, for human follow-up | No automated states; runtime incidents are always marked simulated |
| RL policy | `rl_defense.PolicyRunner` (Double DQN, action masks, Q-values, hash-pinned checkpoint via `verify_rl_checkpoint`), `platform_mapping.facts_from_platform` | Yes | `RouteSignal.source` allows only demo, replay or simulated labels; no out-of-distribution checks; torch is not installed in backend CI |
| Defense Lab UI | `/lab`: Gymnasium simulator playback | Yes | Nothing shows live telemetry |
| Seven agents | Orchestrator, Docker sandbox, Patch, Verify | Yes, through the existing assessment flow | Not linked to live incidents |
| Actions on real systems | None, by design | n/a | Everything in sections 4 to 7 below |

## 2. Required components and where they live

| Component | Location |
|---|---|
| Connected applications, owner grants, telemetry events, live incidents, actions, notifications, worker heartbeats | migration `0009_live_defense`, tables in `backend/db.py` |
| Event schema and normalization | `backend/live_defense/schemas.py` |
| Detection rules (pure, deterministic) | `monitoring/monitoring/detect.py` |
| State machine (pure) | `backend/live_defense/state.py` |
| Observation mapping and RL inference with fallback | `backend/live_defense/policy.py` |
| Independent authorization gate (pure) | `backend/live_defense/authorize.py` |
| Typed action adapters | `backend/live_defense/adapters.py` |
| Orchestration (jobs) | `backend/live_defense/engine.py` |
| Notifications | `backend/live_defense/notify.py` |
| API | `backend/api/live_defense.py` |
| Owned test application | `examples/live-defense-target/` |
| End-to-end demonstration | `scripts/live_defense_demo.py` |
| UI | `frontend/app/(console)/projects/[id]/live-defense`, `/lab` relabelled "Defense Simulator" |

## 3. Flow

```
owned app -> POST /ingest/events (Bearer ingest token) -> security_events (deduplicated)
  -> job live_defense_process -> detect (pure rules) -> correlate into one open incident per (app, category, source)
  -> DETECTED -> TRIAGED (evidence reliability) -> RECOMMENDED (RL policy, else deterministic rules)
  -> authorize (allowlist, owner grant, scope, blast radius, budget, expiry) -> AUTHORIZED or ESCALATED
  -> EXECUTING (adapter, idempotent control id) -> VERIFYING (control state + new telemetry)
  -> RESOLVED, ROLLED_BACK or ESCALATED; control expiry job removes the control; notification each step
```

## 4. Security boundaries (code, not prompts)

1. The policy (RL or rules) only proposes. `authorize.check` is a pure function that reads only the proposal, the owner grants and recorded action history. It never reads model output beyond the action kind and target.
2. Allowlist: `increase_logging`, `rate_limit`, `block_source`, `escalate`, `request_reassessment`. Nothing else has an adapter. Isolation, commands, database changes, credential rotation, code deployment and disabling an application have no code path.
3. Each kind needs an explicit owner grant for that application (owner role, audited). Grants carry a maximum duration and an hourly budget.
4. Blast radius: `block_source` targets exactly one address (no ranges), never loopback, link-local, multicast, unspecified, or an address on the owner's protected list. `rate_limit` targets one route of the connected application and has a floor on the allowed rate.
5. Every control has an expiry no longer than the grant allows; an expiry job removes it.
6. Idempotency: each action row has a unique key `(incident, kind, target)`; the adapter call carries the action id as the control id, and the target upserts by id. A worker crash between the call and the database update replays the same id, so the control exists once.
7. Concurrency: incidents are advanced under `SELECT ... FOR UPDATE`; a partial unique index allows one open incident per correlation key.
8. Adapters talk only to the control URL the owner registered for that application. Requests are signed (HMAC-SHA256 over timestamp and body) with a per-application secret shown once to the owner.
9. Seven-agent work linked to an incident goes through the existing assessment path (authorized scope, sandbox, approval gate). No generated code is deployed.
10. Telemetry is never invented. Each event records `simulated: false` only when it came through an authenticated ingest; events from the drill path keep their simulated label.

## 5. Implementation plan (this slice)

1. Schema and ingestion with tenant isolation, size limits, rate limits and deduplication.
2. Pure detection rules: repeated authentication failures from one source, WAF alerts at high severity, error spikes, scanning patterns (many distinct missing routes from one source), vulnerability findings and deploy or configuration changes (recorded as context, they raise severity of a correlated incident).
3. Policy: map to `PlatformFacts` with live provenance; reject stale, missing or out-of-range inputs; run the hash-verified DDQN when configured; otherwise deterministic rules; record Q-values, ranking, policy version and the reason for any fallback.
4. Authorization gate and adapters (HTTP control adapter for the owned app, internal escalation and reassessment request).
5. Engine jobs with retries and dead letters; verification from new telemetry; expiry and rollback.
6. Webhook notifications with deduplication and a per-application storm limit.
7. API, Live Defense UI, owned test app, end-to-end script, tests.

## 6. Out of scope for this slice

Email delivery, third-party WAF or CDN providers, automatic start of a full seven-agent assessment from an incident (a reassessment request is recorded and notified; a person starts it), production deployment.
