# backend/

> **What exists: nothing yet (Phase 0).** Spec: [docs/13](../docs/13_BACKEND_API_DESIGN.md),
> [docs/04](../docs/04_SYSTEM_ARCHITECTURE.md).

## Purpose
The control plane: HTTP API, authentication, projects and repositories,
authorized scopes and approvals, persistence, job queue, orchestrator host, SSE,
audit log, LLM gateway, artifact store abstraction.

## Responsibilities
- `/api/v1` endpoints in [docs/13](../docs/13_BACKEND_API_DESIGN.md).
- PostgreSQL schema + migrations; repository layer that always scopes by
  `org_id`/`project_id`.
- Job queue (`SKIP LOCKED`, leases) and the `worker` process entrypoint.
- Hosting the orchestrator state machine defined in `security-agents/`
  ([docs/08](../docs/08_AGENT_ORCHESTRATION.md)).
- LLM gateway: the only path to Anthropic; budgets, redaction, structured-output
  validation, record/replay ([ADR-0007](../docs/decisions/0007-claude-llm-gateway.md)).
- Hash-chained audit log; artifact store with SHA-256 addressing.
- Settings from environment ([.env.example](../.env.example)).

**Must not:** execute untrusted code in-process, run long work in request
handlers, bypass the scope guard, merge or deploy code.

## Interfaces
| Direction | Interface |
|---|---|
| Exposes | REST + SSE to `frontend/`; `/webhooks/github` and `/ingest/runtime/{project_id}` to external sources |
| Exposes (Python) | `backend.llm_gateway`, `backend.artifacts`, `backend.persistence` for workers |
| Consumes | `shared/` models; `code_intelligence.api` (read queries); `monitoring` handlers; `security_agents` orchestrator definitions and `scope_guard`; `rl_defense.inference` |
| Data | PostgreSQL (`DATABASE_URL`), artifact store (`ARTIFACT_STORE_URI`) |
| External | GitHub OAuth + App, Anthropic API |

## Dependencies
Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.x + Alembic (proposed),
Anthropic SDK, structlog + OpenTelemetry (proposed), pytest/ruff/mypy.
Upstream tasks: CORE-001 (`shared/`).

## Planned layout
```
backend/
  backend/
    main.py            # FastAPI app factory
    settings.py
    api/v1/            # routers per resource
    auth/              # GitHub OAuth, sessions, CSRF
    persistence/       # models, repositories, migrations (alembic/)
    jobs/              # queue, worker runner, leases
    orchestration/     # host for security_agents state machine, gates
    llm_gateway/       # client, budgets, redaction, record/replay
    artifacts/         # store abstraction
    audit/             # hash-chained log
    sse/
  tests/
  Dockerfile
```

## First tasks
CORE-002 → CORE-004 → CORE-005/006/007/008; CORE-009, CORE-010.

## Commands
None yet. Added by CORE-002.
