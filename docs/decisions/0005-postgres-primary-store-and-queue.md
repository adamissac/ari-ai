# ADR-0005: PostgreSQL as primary store, graph store and job queue

| Field | Value |
|---|---|
| Status | Proposed |
| Date | 2026-10-16 |
| Deciders | UNASSIGNED (ratify in DOCS-002) |
| Related | [architecture/data-flow-and-storage](../architecture/data-flow-and-storage.md), CORE-004, CORE-006 |

## Context
MVP needs relational state, an intelligence graph, an evidence index and a job queue, with no paid infrastructure and minimal operations.

## Decision
PostgreSQL 16 holds all state, graph edges (adjacency tables), audit log and the job queue (`FOR UPDATE SKIP LOCKED` with leases). Large artifacts go to the artifact store. The queue is accessed through an interface so it can be swapped.

## Options considered
| Option | Pros | Cons |
|---|---|---|
| Postgres for everything | One system; transactional jobs with state | Graph traversal queries hand-written; queue throughput limits |
| Postgres + Redis/Celery | Mature queue | Extra service; dual-write consistency |
| Postgres + Temporal | Durable workflows | Heavy for MVP |
| Graph DB (Neo4j) | Native graph queries | Extra service, licensing review |

## Consequences
- Orchestrator transitions and job enqueue commit atomically.
- Graph queries bounded (depth ≤ 3) to stay fast.

## Revisit when
> 10 workers, > 100 jobs/s, or graph queries exceed latency targets (R-09).
