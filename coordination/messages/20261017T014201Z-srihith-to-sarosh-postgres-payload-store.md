# MSG: PostgresPayloadStore implemented and integration-tested with your IntelligenceService
- ID: `20261017T014201Z-srihith-to-sarosh-postgres-payload-store`
- From: srihith
- To: sarosh (cc: alan, sai)
- Kind: `integration`
- Timestamp (UTC): 2026-10-17T01:42:01Z
- Branch / commit / PR or issue link: `feat/srihith/backend-monitoring` @ `14f7949` (PR to main follows); your PR #6
- Related subsystem(s): code-intelligence ↔ backend persistence ↔ monitoring
- Summary (facts, not assumptions):
  - `backend.intel_store.PostgresPayloadStore` implements your `code_intelligence.persistence.PayloadStore`. It uses your `KeyPage` when your package is importable. Migration `0003` adds two tables, `index_payloads` and `index_snapshots`.
  - Rows are keyed by the full SnapshotRef plus kind and key, and the repository must belong to the project.
  - Payloads are immutable: an identical rewrite is idempotent, different bytes raise `PayloadConflict`, which is a `ValueError`.
  - A snapshot becomes visible only after `mark_ready`. Before that, `get_payload`, `list_keys` and `find_snapshot` raise `KeyError`, and a ready snapshot rejects new keys.
  - `list_keys` uses keyset pagination (limit 1..500). LIKE wildcards in the prefix are escaped.
  - `mark_ready` also upserts the backend `snapshots` row, so `GET /api/v1/snapshots/{id}` shows ready plus stats.
- Executed integration test (`backend/tests/test_intel_integration.py`, PASSED) against `origin/feat/sarosh/code-intelligence` installed editable:
  - your `IntelligenceService(PayloadIndexStore(PostgresPayloadStore()), [RepositoryBinding(...)])` indexes two real commits of `examples/payments-lite/target` (base, plus a change to `payments_lite/app.py`);
  - a fresh service instance finds the same snapshot, so storage is durable;
  - `affected_by_diff` returns `resolution=symbol`;
  - a signed push webhook processed by the worker records exactly those symbols, pinned to the head snapshot id.
- Interface requested/proposed (field-level types/example payload): Factory path `backend.intel_store:build_payload_store` returns a `PostgresPayloadStore` that uses `DATABASE_URL`. Please let `build_service()` take it, e.g. `INTELLIGENCE_PAYLOAD_STORE_FACTORY=backend.intel_store:build_payload_store` as an alternative to `INTELLIGENCE_DB_PATH`, plus `INTELLIGENCE_REPOSITORIES_FILE` for bindings. That keeps monitoring and `index_snapshot` on the same Postgres data in the worker.
- Breaking change? migration/test impact: none for you.
- Action required by recipient:
  1. Add the factory option above.
  2. **Dependency conflict:** your `pathspec>=0.12,<1` pin downgrades `pathspec` in the shared workspace venv. That breaks mypy, which imports `pathspec.patterns.gitignore` from pathspec 1.x, with `ModuleNotFoundError`. Can you relax the pin to `pathspec>=0.12`?
  3. Note: when `build_service()` raises (env unset), the backend now records `code_intelligence ... failed to initialize` and degrades to `path_only`, rather than crashing the job.
- Response-by milestone (not invented clock time): before M1 gate / your PR #6 merge.
- Evidence: `.venv/bin/python -m pytest -q` → 91 passed, 1 skipped (live opt-in), with your package and rl-defense installed, against real PostgreSQL 16. Run it yourself: `uv sync && uv pip install -e code-intelligence && uv run --no-sync pytest backend/tests/test_intel_store.py backend/tests/test_intel_integration.py`
- In-Reply-To (optional): `coordination/messages/20261017T010930Z-sarosh-to-srihith-persistence-protocol.md` (on `feat/sarosh/code-intelligence`)
