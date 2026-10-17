# Code intelligence

Persistent, version-aware Python intelligence for review, security agents and monitoring.
Public API: `code_intelligence.api.IntelligenceService`. Public DTOs come directly from
`shared.intelligence` and `shared.evidence`; no consumer needs another indexer.

## What exists

- Full-SHA Git object ingestion, tree hash, pinned ignore rules, generated/vendor/binary
  classification, secret filtering, byte/file/time limits, symlink/submodule exclusion.
  No checkout, import, dependency install or execution of indexed target code.
- Tree-sitter Python syntax validation plus Python AST symbol extraction, complete spans,
  imports, cross-file calls and declared FastAPI/Flask routes/dependencies. Statically
  unambiguous bindings are `exact`, typed receivers and HTTP-test links are `likely`,
  dynamic dispatch stays `unresolved`.
- Test assertions, imperative docstrings/docs and Field constraints become source-cited
  **ambiguous intent**, with confidence and origin. They are not test execution results.
- Ownership intent links to matching routes. A majority of resource-by-id GET siblings
  using the same identity-checking helper can produce a medium-confidence possible
  inconsistency on an outlier, with sibling call-site citations. Ordinary store accessors
  remain graph dependencies and are excluded from authentication signals. Index version
  `python-ast-ts/0.2.0` requires re-indexing older 0.1.0 stores for these improved facts.
- Optional `ClaudeExpectationProvider` uses an injected, budgeted backend gateway with
  at most three turns and no execution tools. Citations/subjects must occur in the supplied
  pack. Inference stays `origin=inferred`, `status=inferred`, confidence 0.3; model, mode,
  usage and tool-call records persist with the index. CI uses FakeTransport. A live attempt
  in this workspace skipped because no authorized key was available.
- Durable SQLite local storage and `PayloadIndexStore` over the agreed backend-owned
  `PayloadStore`. Real PostgreSQL restart and signed-webhook integration tests pass.
- Complete-version checks on every query, bounded graph/BM25 retrieval, whole source spans,
  linked tests/expectations, XML-escaped untrusted delimiters and conservative UTF-8 byte
  accounting for the complete serialized pack. Tiny budgets raise `BUDGET_EXHAUSTED`.
- Two-snapshot impact compares symbol spans, expands both graphs and includes old/new IDs,
  renamed/deleted files, changed expectations and linked test paths. All head facts are
  re-derived; **no cross-SHA artifact is silently carried**. This is safe full recomputation,
  not a parse-cache performance claim.

## Run and test

From repository root (Python 3.12):

```bash
uv sync --frozen
uv run ruff check code-intelligence
uv run ruff format --check code-intelligence
uv run mypy --config-file code-intelligence/pyproject.toml code-intelligence/code_intelligence
uv run pytest -ra code-intelligence/tests backend/tests/test_intel_store.py backend/tests/test_payload_store_intel_integration.py
```

Backend tests start real local PostgreSQL through `pgserver`, or use `TEST_DATABASE_URL`.
They create a disposable test database. CI uses a PostgreSQL service and no live key.
Optional live inference: `RUN_LIVE_LLM_EVAL=1 uv run pytest -s -m live_llm code-intelligence/tests/test_inference.py`.
It sends only the owned synthetic fixture and never prints a key.

## Worker configuration

Set `INTELLIGENCE_REPOSITORIES_FILE` to a trusted JSON registration file:

```json
[{"project_id":"prj_example00","repo_id":"rep_example00","full_name":"owned/payments","local_path":"/approved/local/git/repo","include_prefix":"examples/payments-lite/target"}]
```

Set exactly one persistence option:

- `INTELLIGENCE_PAYLOAD_STORE_FACTORY=backend.intel_store:build_payload_store` plus the
  backend's `DATABASE_URL` (migrations through `0003` required), or
- `INTELLIGENCE_DB_PATH=/private/local/intelligence.sqlite` for local development.

The factory is `code_intelligence.api:build_service`. Registration is administrator data,
not repository instructions. No implicit remote clone or in-memory success fallback.
`include_prefix` keeps answer keys/labels outside the indexed target. Citations retain
original repository-relative paths and the original commit SHA.

## Consumer API

```python
from code_intelligence.api import build_service
from shared.intelligence import ContextPackRequest, ContextPurpose

intel = build_service()
ref = intel.index_repository(project_id, repo_id, commit_sha)
pack = intel.build_context_pack(
    ContextPackRequest(
        snapshot_ref=ref,
        purpose=ContextPurpose.scout,
        focus=["/payments/{payment_id}"],
        token_budget=24_000,
    )
)
impact = intel.affected_by_diff(repo_id, base_sha, head_sha)
```

`get_symbol(ref, id_or_qualified_name)`, `symbols`, `entry_points`, `expectations` support
scoped queries (list pagination: offset and limit 1..500). `graph_neighbors` limits depth
0..3. `read_chunk` and `search` return delimited canonical ContextChunks with citations.
`read_span` is a low-level redacted text accessor; tools should expose `read_chunk`.
Finding IDs are not seeds yet; consumers must resolve them to symbol/expectation/route IDs.

Backend adapter: `index_snapshot(Snapshot, repo_full_name) -> Snapshot`. Monitoring uses
`affected_by_diff(repo_id, base_sha | None, head_sha)`; missing versions raise so monitoring
can record an honest `path_only` fallback. Do not substitute current working-tree content.

The checked-in [context fixture](fixtures/payments-context-pack.json) validates against
canonical shared V0; [evidence](evidence/m1-payments-lite.json) records its source SHA,
coverage, resolution counts, actual local timing and context budget. Regenerate with:

```bash
uv run python -m code_intelligence.evaluate --repository . --sha <full-known-sha> \
  --prefix examples/payments-lite/target \
  --evidence code-intelligence/evidence/m1-payments-lite.json \
  --pack code-intelligence/fixtures/payments-context-pack.json
```

## Limits and remaining integration

Python is implemented; JS/TS is MVP stretch. Routes are declarations, not runtime reachability;
router mounts/prefix composition, inherited auth conventions and dynamic targets are not
resolved. No repository content can confirm its own rules. Authenticated human confirmation
and conflict adjudication require the backend intent-decision API. Findings/regression artifact
joins remain backend-owned; `regression_tests` currently names statically linked existing test
paths, not promoted verified-repair test records. Large indexes load as one typed payload;
partitioned persistence and incremental parser caching remain performance follow-ups.

Sai and Alan still need to replace temporary consumer adapters with this service; their
complete runtime integration is not claimed by producer contract tests. No target security
probe, target test execution, production deployment or live-model proof is implied here.
