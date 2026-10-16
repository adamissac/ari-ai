# ADR-0004: Contract-first: Pydantic → JSON Schema → TypeScript

| Field | Value |
|---|---|
| Status | Proposed |
| Date | 2026-10-16 |
| Deciders | UNASSIGNED (ratify in DOCS-002) |
| Related | [12](../12_DATA_MODELS_AND_CONTRACTS.md), CORE-001, CORE-003 |

## Context
Python and TypeScript must agree on dozens of models; LLM outputs must be validated against the same models.

## Decision
Pydantic v2 models in `shared/` are the single source of truth. JSON Schema and TypeScript types are generated into `shared/generated/` and committed; CI fails if regeneration produces a diff. LLM output schemas are derived from the same models.

## Options considered
| Option | Pros | Cons |
|---|---|---|
| Pydantic source of truth | Native validation in Python; LLM schema reuse | TS types are generated, not idiomatic hand-written |
| JSON Schema source of truth | Language-neutral | Hand-written schemas are verbose; Python models generated |
| OpenAPI only | Built into FastAPI | Doesn't cover queue/agent payloads |

## Consequences
- Contract changes follow the order in AGENTS.md §12.
- Generated files are never hand-edited (`.gitattributes` marks them).

## Revisit when
A non-Python producer of contracts appears.
