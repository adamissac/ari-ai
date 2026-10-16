# code-intelligence/

> **What exists: nothing yet (Phase 0).** Spec: [docs/05](../docs/05_CODE_INTELLIGENCE_ENGINE.md),
> internals: [docs/architecture/code-intelligence](../docs/architecture/code-intelligence.md),
> shared layer: [docs/11](../docs/11_SHARED_CONTEXT_AND_MEMORY.md).

## Purpose
The write side of the Unified Intelligence Layer: version-aware structure,
graphs, entry points, behavioral expectations, and context-pack retrieval for a
repository snapshot.

## Responsibilities
- Ingest a repo at a commit SHA into a worker workspace (never execute it).
- Parse with Tree-sitter (Python first; JS/TS stretch); extract symbols,
  imports, calls (with resolution confidence), framework entry points with auth
  dependencies.
- Derive `BehavioralExpectation`s with provenance and confidence.
- Build bounded, provenance-tagged, untrusted-delimited `ContextPack`s.
- Incremental indexing and `affected_by_diff` → `ImpactSet`.

**Must not:** call runtime agents, own review logic, execute repository code.

## Interfaces (planned `code_intelligence/api.py`)
| Function | Consumers |
|---|---|
| `index_snapshot(repo_id, commit_sha, base_snapshot_id=None)` | orchestrator, monitoring |
| `get_symbol`, `entry_points`, `expectations` | review, agents, backend read API |
| `build_context_pack(ContextPackRequest)` | review, agents |
| `affected_by_diff(base, head) -> ImpactSet` | monitoring |
| Read-only tools `code.read_span`, `code.search`, `graph.*`, `expectations.for_subject` | registered in `security-agents` tool registry |

## Dependencies
`shared/` models; `backend` persistence + LLM gateway (for expectation
inference); Tree-sitter + Python grammar; BM25 implementation (e.g. `rank-bm25`,
proposed). No vector DB ([ADR-0010](../docs/decisions/0010-no-vector-db-for-mvp.md)).

## Planned layout
```
code-intelligence/
  code_intelligence/
    api.py  fetch/  classify/  parse/  queries/python/  extract/
    frameworks/  expectations/  graph/  retrieval/  incremental/  store/
  tests/ (golden fixtures per language)
```

## First tasks
INTEL-001 … INTEL-008.

## Commands
None yet.
