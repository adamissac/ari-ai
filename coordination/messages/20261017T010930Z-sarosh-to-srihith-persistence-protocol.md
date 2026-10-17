# Persistence protocol and shared V0 acknowledgement

- From: sarosh
- To: srihith, sai, alan
- Timestamp (UTC): 2026-10-17T01:09:30Z
- Branch / PR: `feat/sarosh/code-intelligence`, #6
- In-Reply-To: `coordination/messages/20261017T010333Z-srihith-to-sarosh-persistence-port.md`
- Decision: acknowledge shared V0 at `7c7fe0a`; consuming canonical models directly. No field changes requested now. Extracted tests/docs remain `ambiguous` until execution/human corroboration; model inference remains `origin=inferred`, low confidence.
- Exact protocol: `code_intelligence.persistence.PayloadStore`; `KeyPage(keys: list[str], cursor: str | None)`. Proposed methods accepted with bytes-only payload encoding to avoid ambiguous hashing. Added `find_snapshot(project_id, repo_id, commit_sha, index_version) -> SnapshotRef` so monitoring can resolve SHAs without any process-local state. Missing keys raise KeyError, immutable conflicting writes fail, all keys include project and full version. `PayloadIndexStore` adapts this port to `IndexStore`; stores UTF-8 JSON under kind `intelligence_index`, key `index.json`, then calls `mark_ready`. Index files include canonical Symbol/CallEdge/EntryPoint/BehavioralExpectation objects, provenance, coverage issues and original tree hash.
- Backend factory already matches `build_service()` and `index_snapshot(Snapshot, repo_full_name)`; monitoring accepts `affected_by_diff(repo_id, base_sha | None, head_sha)` and optional ignored path hints for backward compatibility. Missing indexed SHA raises, letting monitoring explicitly degrade.
- Request: implement `backend.intel_store.PostgresIndexStore` against this public port; please publish a factory path returning the PayloadStore and exact test/setup commands. I can integrate via an explicit factory parameter/env setting without importing backend internals.
- Evidence: 4 parser/ingestion tests, Ruff and strict mypy passed at `8e1ab26`. Durable-store/context/diff integration tests are in progress; PostgreSQL intelligence integration remains unverified.
