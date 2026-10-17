# 05 — Code intelligence engine

Status: **Python producer implemented; full consumer integration in progress**.
See [implementation and executed evidence](../code-intelligence/README.md). Tree-sitter
validates syntax; AST supplies structural metadata. Head facts are fully re-derived;
parse caching/carry-forward remain performance follow-ups. Directory: `code-intelligence/`. Deep dive:
[architecture/code-intelligence](architecture/code-intelligence.md).

## Purpose

Build and maintain the version-aware understanding of a repository that every
other subsystem uses: what exists (structure), how it connects (graphs), what it
is supposed to do (behavioral expectations), and how to retrieve the right
slice of it for a task (context packs). It is the write side of the Unified
Intelligence Layer described in [11](11_SHARED_CONTEXT_AND_MEMORY.md).

## Inputs

| Input | Source |
|---|---|
| `Snapshot` request: `(repo_id, commit_sha)` | Orchestrator or monitoring |
| Repository contents at that SHA | GitHub App clone into a worker workspace (read-only for analysis) |
| Previous snapshot (optional) | Data plane, for incremental indexing |
| User edits to expectations | Backend API |

## Outputs (all in `shared/`, see [12](12_DATA_MODELS_AND_CONTRACTS.md))

- `Snapshot` (status, language stats, index version)
- `FileNode`, `Symbol` (function, method, class, module), `ImportEdge`,
  `CallEdge` (with resolution confidence), `EntryPoint` (HTTP route, CLI, job)
- `DependencyManifest` (declared third-party packages + versions)
- `BehavioralExpectation`
- `ContextPack` (retrieval result)

## Pipeline

1. **Fetch** — shallow clone at SHA into `workspaces/<snapshot_id>/` on the
   worker; record tree hash. Repo content is never executed during indexing.
2. **Classify files** — language, generated/vendored/test detection via path
   rules and headers.
3. **Parse** — Tree-sitter (Python first; JS/TS stretch) into syntax trees.
4. **Extract symbols** — qualified names, spans, signatures, decorators,
   docstrings (INTEL-003 for Python).
5. **Build graphs** — imports, calls (static resolution with confidence:
   `exact`, `likely`, `unresolved`), inheritance.
6. **Detect entry points** — framework adapters (FastAPI, Flask first) map
   routes → handler symbols, including auth dependencies/decorators.
7. **Derive expectations** — see below.
8. **Persist** — bulk insert keyed by `snapshot_id`; mark snapshot `READY`.

## Behavioral expectations

An expectation is a falsifiable statement about intended behavior:

```
id: exp_…
snapshot_id: snp_…
subject: symbol or entry point (e.g. GET /payments/{payment_id})
statement: "A customer can only read payments they own."
kind: authorization | invariant | input_validation | state_transition | error_handling | other
sources: [EvidenceRef…]   # test file lines, docstring, README section, decorator
confidence: high | medium | low
origin: extracted | inferred_by_llm | user_confirmed
status: proposed | confirmed | rejected
```

Sources, in decreasing trust: user-confirmed → existing tests → explicit
docs/docstrings/types → framework conventions (auth dependency present on sibling
routes) → LLM inference over code. LLM-inferred expectations are always
`confidence: low` until confirmed or corroborated by another source, and the LLM
must cite the code spans it used (validated: cited spans must exist).

## Retrieval: context packs

Agents never receive whole repositories. A `ContextPackRequest` names a task
(e.g. `scout.authorization`), seeds (symbols, entry points, finding IDs) and a
token budget. The retriever:

1. expands seeds over the call graph (bounded depth, default 2),
2. adds relevant expectations, prior findings and their regression tests,
3. ranks by graph distance + lexical match (BM25 over symbol names/docstrings),
4. truncates to budget, preferring whole symbols over partial ones,
5. returns code inside explicit untrusted-data delimiters with provenance per
   chunk ([15](15_SECURITY_BOUNDARIES.md) §prompt injection).

No vector store in MVP ([ADR-0010](decisions/0010-no-vector-db-for-mvp.md)).

## Freshness

Facts are keyed by `snapshot_id`. When a new snapshot is indexed incrementally,
facts for unchanged files are carried forward with `carried_from` set; facts
whose source spans or call neighborhoods intersect the diff are re-derived.
Expectations whose sources changed become `status: proposed` again.

## Public interface (`code_intelligence/api.py`, planned)

| Function | Purpose |
|---|---|
| `index_snapshot(repo_id, commit_sha, base_snapshot_id=None) -> SnapshotId` | Run the pipeline (worker job) |
| `get_symbol(snapshot_id, qualified_name) -> Symbol` | Lookup |
| `entry_points(snapshot_id) -> list[EntryPoint]` | Attack surface for Scout |
| `expectations(snapshot_id, subject=None) -> list[BehavioralExpectation]` | P1/P2/P3 consumers |
| `build_context_pack(req: ContextPackRequest) -> ContextPack` | Retrieval |
| `affected_by_diff(base_snapshot_id, head_snapshot_id) -> ImpactSet` | Monitoring |

## Non-goals

Executing repository code, dynamic analysis, full type inference, cross-repo
graphs (later).

## Open questions

RQ-002 (how accurate is LLM-inferred expectation extraction?), RQ-003 (call
resolution accuracy for dynamic Python). See
[research/RESEARCH_QUESTIONS](research/RESEARCH_QUESTIONS.md).
