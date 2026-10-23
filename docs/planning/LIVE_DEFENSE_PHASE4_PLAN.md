# Live Defense Phase 4 plan (4.0)

Status: **implemented** on `feat/live-defense-phase4-controlled-enforcement`.
This is the **controlled enforcement** slice for an **owned test environment**
only. Phase 5 autonomous / customer-production enforcement is out of scope.

Base: `origin/main` at merge of Phase 3 PR #392 (`5be62de`). Codex owns RL
research. This work does not train, promote, or edit v6 weights, datasets, or
the promotion registry.

Phase 3 on main is compatible: `LivePolicyDecision.enforcement` stays
`NOT_EXECUTED`, `AnalystReview.accept` stays non-executing, NIST incident
statuses are untouched. Phase 4 **extends** those records with a separate
control lifecycle and a separate authorization endpoint.

## Trust-boundary diagram

```
                    untrusted data                         trusted control plane
 ┌───────────────────────────────┐            ┌──────────────────────────────────┐
 │ Owned test app (loopback)     │            │ API process                      │
 │  payments-lite control fixture│  HMAC+idemp│  review POST  ≠  authorize POST  │
 │  TTL local to the app         │◄───────────│  authorize.check (pure, 15)      │
 └────────────▲──────────────────┘  no arb URL│  never LLM / never v6 / never NN │
              │ verify with real HTTP         └──────────────┬───────────────────┘
              │ (HTTP 200 from adapter ≠ effect)             │ enqueue
              │                                 ┌────────────▼───────────────────┐
 ┌────────────┴──────────────────┐              │ Worker (existing SKIP LOCKED)  │
 │ Analyst browser               │              │ execute → verify → expire      │
 │  accept/reject = opinion only │              │ rollback / emergency stop      │
 │  Authorize control = gate     │              └────────────────────────────────┘
 │  no /block /isolate /rate-limit
 │  that bypasses the gate       │
 └───────────────────────────────┘
```

Review, authorization, execution, and verification are **distinct operations**:

| Operation | Who | Endpoint / job | Can move traffic? |
|---|---|---|---|
| Review | project member | `POST .../reviews` (Phase 2/3) | No |
| Authorization | project owner session | `POST .../control-authorizations` | No (records `authorized` only) |
| Execution | worker after `authorized` | job `live_defense_execute` | Adapter apply to registered app |
| Verification | worker | job `live_defense_verify` | Probes real requests; rollback on fail |

A recommendation (`LivePolicyDecision`) has no transition into `executing`.
RL / rules may **propose**; they cannot authorize or execute.

## Order of work

| Step | Scope |
|---|---|
| 4.0 | This plan + contracts 0.18.0 (additive) + ADR-0019 |
| 4.1 | `LiveControl` lifecycle, validated transitions, row locks, audit |
| 4.2 | `authorize.check` — 15 deterministic checks, fail closed |
| 4.3 | Allowlisted kinds A–D only; abstain+escalate otherwise |
| 4.4 | Signed loopback adapter, existing job queue |
| 4.5 | Separate authorize UI/API; Phase 2/3 accept unchanged |
| 4.6 | Verify actual effect; unresolved control blocks further actions |
| 4.7 | App-local TTL + emergency stop |
| 4.8 | Controls dashboard |
| 4.9 | 20 owned-fixture scenarios |
| 4.10 | Honest eval scorecard |
| 4.11 | Security tests, lint, typecheck, build, gitleaks |

## Explicit non-goals (do not begin Phase 5)

- Autonomous enforcement (no human authorization)
- Customer production grants
- Isolation, credential rotation, prod firewall, code deploy, DB mutation, auto-patch
- Training, dataset, v6 weight, or promotion-registry edits
- Browser-supplied adapter destinations
- Overloading NIST SP 800-61r3 incident statuses
