# Code intelligence — internals

Status: **specified**. Product-level spec: [05](../05_CODE_INTELLIGENCE_ENGINE.md).

## Module layout (planned, `code-intelligence/code_intelligence/`)

| Module | Responsibility |
|---|---|
| `api.py` | Public functions (see 05) |
| `fetch/` | GitHub App clone at SHA, workspace management, tree hash |
| `classify/` | Language, generated/vendored/test detection |
| `parse/` | Tree-sitter loading, per-language query files (`queries/python/*.scm`) |
| `extract/` | Symbols, imports, calls, decorators per language |
| `frameworks/` | Entry-point adapters: `fastapi.py`, `flask.py` (MVP), `express.py` (stretch) |
| `expectations/` | Extractors (tests, docstrings, decorators, conventions) + LLM inference with citation validation |
| `graph/` | Call/import graph persistence and queries (`neighbors`, `paths_to`) |
| `retrieval/` | Context pack builder, BM25 index per snapshot |
| `incremental/` | Diff → affected files/symbols; carry-forward |
| `store/` | Persistence through the shared repository layer |

## Indexing data flow

```mermaid
flowchart LR
  A[fetch @SHA] --> B[classify]
  B --> C[parse: tree-sitter]
  C --> D[extract symbols/imports/calls]
  D --> E[framework adapters → EntryPoints]
  D --> F[graph build + resolution]
  E --> G[expectation extractors]
  F --> G
  G --> H[LLM expectation inference (cited spans validated)]
  H --> I[(persist, snapshot READY)]
  I --> J[BM25 index build]
```

## Call resolution (Python)

1. Local scope and imports → `exact`.
2. `self.method` within class hierarchy → `exact`/`likely`.
3. Attribute on parameter with type hint → `likely`.
4. Dynamic dispatch, `getattr`, decorators that wrap → `unresolved` with
   `callee_name` kept for lexical retrieval.

## Expectation extractors (MVP order)

| Extractor | Signal | Confidence |
|---|---|---|
| `tests` | assertion names/bodies over a subject (e.g. `test_customer_cannot_read_other_payment`) | high |
| `docstring` | imperative statements ("must", "only", "never") | medium |
| `auth_convention` | sibling routes share an auth dependency; one route lacks it | medium (flagged as possible inconsistency) |
| `types_constraints` | Pydantic field constraints (`gt=0`) | medium |
| `llm_inference` | model proposal with ≥ 1 cited span that exists | low |

## Incremental indexing

`affected_by_diff`: changed files → changed symbols (span overlap) → 1-hop
callers/callees → expectations with these subjects or sources → findings with
these subjects → regression tests targeting them. Unchanged facts copied with
`carried_from`.

## Performance targets (unmeasured)

Parse ~ 5k LOC/s per core; 50k LOC repo < 2 min including expectations
(LLM inference limited to top-N entry points).
