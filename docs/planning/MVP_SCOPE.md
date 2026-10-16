# MVP scope (HackATL)

Status: **specified**. Requirements: [03](../03_PRODUCT_REQUIREMENTS.md) (priority M).

## The MVP in one sentence

On our own deliberately vulnerable Python service (`examples/payments-lite`), the
platform runs the full loop — understand, review, test, validate safely,
diagnose, repair, verify, monitor, learn — and every claim in the UI links to
executed evidence.

## In scope

| Area | Included |
|---|---|
| Languages | Python (FastAPI/Flask) |
| Repos | One connected GitHub repo (demo target), via GitHub App |
| Targets | Sandbox build of the connected repo only |
| P1 | Indexing, expectations (extracted + LLM-inferred low-confidence), review, generated tests, repair |
| P2 | All seven agents; check library with ownership and bounds categories |
| P3 | Push webhooks → impact → targeted re-assessment / regression rerun; RL env + DDQN + baselines + protocol eval; recommendations panel |
| UI | Scope, timeline, findings, evidence chain, approvals, patch/verify, monitoring |
| Infra | Local Docker Compose; no hosted deployment required |

## Out of scope (MVP)

JS/TS indexing (stretch), external/staging targets, runtime telemetry from real
systems, PR auto-comments (stretch), multi-org RBAC, hosted sandboxes, gVisor,
vector search, auto-merge (never), any real-world RL action (never).

## Cut order if time runs short

1. FR-3-04 runtime log signals → show monitoring on code events only.
2. Fortify → report recommends hardening via Diagnose notes only.
3. FR-2-08 PR creation → show diff + verification only.
4. RL UI panel → RL results shown as protocol table on a slide.
Never cut: scope check, sandbox controls, Verify independence, evidence links.

## Demo acceptance

Matches the storyline in [20](../20_DEMO_SCRIPT.md) and IC-9 in
[25](../25_INTEGRATION_STRATEGY.md).
