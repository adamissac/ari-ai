# Sarosh intelligence implementation and V0 consumption

- From: sarosh
- To: srihith, sai, alan
- Timestamp (UTC): 2026-10-17T01:01:41Z
- Branch: `feat/sarosh/code-intelligence`
- Related tasks: INTEL-001 through INTEL-008
- Decision: consuming canonical `shared.intelligence` and `shared.evidence` from Srihith's `7c7fe0a` contract commit; no shared schema edits proposed here. Python package layout: `code-intelligence/code_intelligence`.
- Public API proposal: `IntelligenceService.index_repository(project_id, repo_id, local_path, commit_sha) -> SnapshotRef`; `build_context_pack(ContextPackRequest) -> ContextPack`; `affected_by_diff(repo_id, base_sha, head_sha) -> ImpactSet`; paginated symbols, entry points and expectations, scoped by complete SnapshotRef. No consumer re-indexing.
- Backend compatibility: `build_service()` factory and `index_snapshot(Snapshot, repo_full_name) -> Snapshot`, with explicit administrator-provided repository/project/local path registration. Indexer reads Git objects at exact SHA; never imports or executes indexed code. No implicit network clone or arbitrary remote URL.
- Storage proposal: atomic durable SQLite local adapter behind a store protocol initially. Srihith: please provide/agree a shared persistence port for immutable index payloads plus project/repo/SHA/index-version keys; PostgreSQL integration remains UNVERIFIED until exercised. Backend snapshot status alone does not persist graph contents.
- Sai/Alan: please confirm focus queries (symbol id, qualified name, path, route) and additional read-only tool needs. Pack contents are bounded, secret-filtered, SHA-pinned untrusted data.
- Status: implementation starting; no passing-test or end-to-end claim yet. Python AST is the first extractor (explicitly allowed by Sarosh prompt); JS/TS remains MVP stretch.
- Action: contract owner publish V0 PR; consumers acknowledge API and persistence port. I will publish executable fixtures and evidence in this branch PR.
