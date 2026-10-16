# ADR-0002: Python 3.12 + FastAPI + Pydantic v2 for backend and agents

| Field | Value |
|---|---|
| Status | Proposed |
| Date | 2026-10-16 |
| Deciders | UNASSIGNED (ratify in DOCS-002) |
| Related | [13](../13_BACKEND_API_DESIGN.md) |

## Context
Tree-sitter bindings, the Anthropic SDK, PyTorch and Gymnasium are first-class in Python. The team wants one backend language.

## Decision
Backend API, workers, code intelligence, review, agents, monitoring and RL are Python 3.12. HTTP via FastAPI; models via Pydantic v2; migrations via Alembic; ORM/query layer via SQLAlchemy 2.x (proposed). Frontend stays TypeScript.

## Options considered
| Option | Pros | Cons |
|---|---|---|
| Python + FastAPI | Ecosystem fit (ML, parsing, LLM SDK); Pydantic schemas | GIL for CPU-bound work (mitigated by worker processes) |
| TypeScript everywhere | One language with frontend | Weaker ML/RL ecosystem |
| Go backend + Python workers | Performance | Two backend languages; duplicated contracts |

## Consequences
- OpenAPI generated automatically for frontend client generation.
- CPU-heavy indexing runs in worker processes, not the API.

## Revisit when
API latency or concurrency becomes a measured bottleneck.
