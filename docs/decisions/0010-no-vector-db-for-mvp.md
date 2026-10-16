# ADR-0010: No vector database for MVP

| Field | Value |
|---|---|
| Status | Proposed |
| Date | 2026-10-16 |
| Deciders | UNASSIGNED (ratify in DOCS-002) |
| Related | [05](../05_CODE_INTELLIGENCE_ENGINE.md), INTEL-007, INTEL-103 |

## Context
Context packs need relevant code. Embedding pipelines add infrastructure, cost and opacity.

## Decision
MVP retrieval uses call-graph expansion plus BM25 lexical ranking over symbol names, docstrings and identifiers. No embeddings or vector DB. pgvector is the first option if recall proves insufficient.

## Options considered
| Option | Pros | Cons |
|---|---|---|
| Graph + BM25 | No infra; explainable; deterministic | Misses semantic similarity |
| pgvector | Same DB; semantic recall | Embedding cost + pipeline |
| Dedicated vector DB | Scale | Extra service |

## Consequences
- Retrieval quality must be measured on fixtures (RQ-004).

## Revisit when
Measured recall of needed context below target on fixtures.
