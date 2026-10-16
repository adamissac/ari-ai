# Architecture Decision Records

ADRs record decisions with lasting consequences. Template:
[0000-template](0000-template.md). Statuses: `Proposed` → `Accepted` |
`Rejected`; later `Superseded by ADR-NNNN` or `Deprecated`.

**All ADRs below are `Proposed`.** They capture the working defaults written into
[AGENTS.md](../../AGENTS.md) §7 and must be ratified by the team (`DOCS-002`)
before Phase 1 implementation relies on them.

| ADR | Title | Status |
|---|---|---|
| [0001](0001-monorepo-layout.md) | Monorepo with one package per subsystem | Proposed |
| [0002](0002-python-fastapi-backend.md) | Python 3.12 + FastAPI + Pydantic v2 for backend and agents | Proposed |
| [0003](0003-deterministic-orchestrator.md) | Deterministic state-machine orchestrator | Proposed |
| [0004](0004-contract-first-shared-models.md) | Contract-first: Pydantic → JSON Schema → TypeScript | Proposed |
| [0005](0005-postgres-primary-store-and-queue.md) | PostgreSQL as primary store, graph store and job queue | Proposed |
| [0006](0006-docker-sandbox-no-network-default.md) | Hardened Docker sandboxes, no network by default | Proposed |
| [0007](0007-claude-llm-gateway.md) | Anthropic Claude behind a single LLM gateway | Proposed |
| [0008](0008-offline-double-dqn.md) | Offline Double DQN in a Gymnasium simulator; recommendations only | Proposed |
| [0009](0009-github-app-integration.md) | GitHub App for repository access and webhooks | Proposed |
| [0010](0010-no-vector-db-for-mvp.md) | No vector database for MVP | Proposed |

## Process

1. Copy the template to `NNNN-short-title.md` (next number).
2. Open a PR labelled `adr`; link affected specs.
3. Decide in review; set status, date and deciders.
4. Update specs that the decision changes in the same PR.
