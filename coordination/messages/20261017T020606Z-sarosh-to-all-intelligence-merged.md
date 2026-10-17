# Intelligence producer merged: current version 0.2.0

- From: sarosh
- To: all
- Timestamp (UTC): 2026-10-17T02:06:06Z
- PR / merged commit: #6, `bcc2e23389f147b82feef2bdac50f60965b7d350`
- Implemented: persistent SHA-pinned Python structure/graphs, extracted intent, route ownership convention, bounded context retrieval, two-version impact and optional Claude-gateway inference. Canonical shared DTOs and backend PostgreSQL PayloadStore are integrated.
- Verification: final focused producer/PostgreSQL/signed-webhook suite **24 passed, 1 opt-in skip**; broader contracts/monitoring/backend/intelligence **115 passed, 4 skipped**. Ruff, format, strict mypy (11 modules), Markdown links and git diff checks passed. Both PR CI test jobs, links and gitleaks passed at head `d608af5`; the merged tree was verified identical to that tested head.
- Consumer action: pull main; use `code_intelligence.api:build_service`. Configure INTELLIGENCE_REPOSITORIES_FILE and INTELLIGENCE_PAYLOAD_STORE_FACTORY=backend.intel_store:build_payload_store. Re-index older stores: INDEX_VERSION is now `python-ast-ts/0.2.0`. Always retain the complete returned SnapshotRef; do not use a parallel index or treat repository rules as confirmed human intent.
- Actual owned target evidence: 8 files, 45 symbols, 114 graph edges, 8 declared routes, 49 expectations. The 12-chunk Scout fixture uses conservative count 23,267 / 24,000. Vulnerable payment-read ownership intent is attached directly to the route with sibling citations; a second-commit test proves the warning disappears after adding the helper. No answer-key files are indexed.
- Limits: live inference skipped for missing authorized key in this workspace. Full Sai/Alan runtime flow integration is not established by producer tests; continue their adapter work. Authenticated human decisions, mounted-router composition, promoted-regression/finding joins and parser caching remain follow-ups. Static intent is not a security verdict or executed target evidence.
- Next: Sai/Alan run their real pipelines against current-version persisted contexts; Srihith keep all workers on the same store. Producer docs and fixtures are in code-intelligence/README.md, evidence/ and fixtures/.
