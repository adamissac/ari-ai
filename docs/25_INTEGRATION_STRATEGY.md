# 25 — Integration strategy

Status: **specified**. How independently built subsystems become one loop
without a big-bang merge.

## Approach

1. **Contracts first** (`CORE-001`, `CORE-003`): the shared models exist before
   subsystems that exchange them.
2. **Walking skeleton early**: a thin end-to-end path with stubbed internals
   (fake LLM, trivial agents) passes before any subsystem is deep.
3. **Fixtures as integration currency**: each producer publishes fixture outputs
   (JSON validated against `shared/`) into `tests/fixtures/`; consumers develop
   against them before the producer is live.
4. **Checkpoints**: named, testable milestones. Once passed, a checkpoint's test
   runs in CI and must stay green.

## Integration checkpoints

| ID | Checkpoint | Proven by | Depends on |
|---|---|---|---|
| IC-1 | Contracts compile: Pydantic models → JSON Schema → TS types, contract tests green | `tests/contract/` | CORE-001, CORE-003 |
| IC-2 | Walking skeleton: create project → start assessment → orchestrator walks all states with fake agents → UI shows timeline via SSE | `tests/integration/test_walking_skeleton.py` | CORE-002, CORE-006, SEC-012, UI-003 |
| IC-3 | Index demo target: snapshot ready with entry points + ≥ 2 expectations incl. ownership rule | integration test on `examples/payments-lite` | INTEL-001…006, DEMO-001 |
| IC-4 | Sandbox boundary: SB-01…SB-06 pass | `tests/security/` | SEC-003, SEC-004, CORE-007 |
| IC-5 | P1 slice: functional finding validated by generated test; repair verified | integration test | REVIEW-001…003, SEC-010 |
| IC-6 | P2 slice: Scout → Probe → Trace → Diagnose → Patch → Verify on authorization weakness, with recorded LLM responses | integration test | SEC-005…011 |
| IC-7 | P3 slice: replayed push webhook → ImpactSet → targeted re-assessment → regression test run | integration test | MON-001…003, INTEL-008 |
| IC-8 | RL: DDQN + baselines evaluated per [17](17_RL_EVALUATION_PROTOCOL.md); recommendation visible in UI | eval summary + UI e2e | RL-001…005, UI-007 |
| IC-9 | Demo e2e: full storyline from [20](20_DEMO_SCRIPT.md) on clean stack | `tests/e2e/` | TEST-005 |

## Interfaces between subsystems

| Producer → Consumer | Contract | Mechanism |
|---|---|---|
| code-intelligence → code-review / security-agents | `ContextPack`, `BehavioralExpectation`, `EntryPoint` | Python `api.py` call in worker |
| code-intelligence → monitoring | `ImpactSet` | `api.py` call |
| code-review / agents → backend | `Finding`, `AgentRun`, artifacts | DB writes via repository layer in `backend` (shared persistence module) |
| backend → worker | Job rows | Postgres queue |
| backend → frontend | REST + SSE | OpenAPI-generated client |
| monitoring → orchestrator | `ReassessmentRequest` | backend service call |
| rl-defense → backend | `DefenseRecommendation`, `RLCheckpoint` | inference function called by backend; offline training writes artifacts |
| GitHub → monitoring | webhook payloads | HTTPS, HMAC |

## External integrations

| System | Purpose | Least privilege |
|---|---|---|
| GitHub App | Clone, webhooks, PR creation | Contents: read (write only on PR branches when user opens PR), Pull requests: write, Metadata: read, Webhooks: push, pull_request |
| GitHub OAuth | Sign-in | `read:user` only |
| Anthropic API | LLM | Server-side key only |

## Branch and merge strategy during integration

Short-lived branches; merge to `main` daily; feature flags (env/config) hide
incomplete subsystems from the UI rather than long-lived branches.
