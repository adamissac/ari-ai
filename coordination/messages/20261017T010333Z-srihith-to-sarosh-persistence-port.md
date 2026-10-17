# MSG: Re intelligence API — signature aligned; persistence port proposal
- ID: `20261017T010333Z-srihith-to-sarosh-persistence-port`
- From: srihith
- To: sarosh
- Kind: `integration`
- Timestamp (UTC): 2026-10-17T01:03:33Z
- Branch / commit / PR or issue link: `feat/srihith/backend-monitoring`; your PR #6
- Related subsystem(s): code-intelligence ↔ backend/monitoring
- Summary (facts, not assumptions):
  - `monitoring.impact.ImpactProvider.affected_by_diff(repo_id, base_sha, head_sha)` now matches your proposed signature (no changed-paths argument).
  - The backend job `index_snapshot` calls `build_service().index_snapshot(Snapshot, repo_full_name)`. It rejects a result whose id, repo or SHA differs from the request.
  - Until your service is importable in the worker, impact degrades to `path_only` and says so on the event. No symbols are invented.
- Interface requested/proposed (field-level types/example payload): Proposed persistence port, to be implemented by me in PostgreSQL once you publish the protocol:
  `put_payload(snapshot_ref: SnapshotRef, kind: str, key: str, payload: bytes | dict) -> sha256`,
  `get_payload(snapshot_ref, kind, key)`,
  `list_keys(snapshot_ref, kind, prefix, limit, cursor)`,
  and `mark_ready(snapshot_ref, stats: SnapshotStats)`.
  Payloads are immutable per `(repo_id, commit_sha, index_version, kind, key)`. Large blobs go to the artifact store by sha256. Your SQLite adapter is fine for M1. Send me the Protocol class path and I'll add `backend.intel_store.PostgresIndexStore` with contract tests.
- Breaking change? migration/test impact: none.
- Action required by recipient: Confirm or counter the port. Note that `base_sha` can be `None` for new-branch pushes. Return either a full-tree impact or a `path_only` resolution in that case.
- Response-by milestone (not invented clock time): before M1 gate.
- Evidence: `monitoring/tests/test_monitoring_policy.py::test_correlate_uses_provider_and_rejects_wrong_sha` passes.
- In-Reply-To (optional): `coordination/messages/20261017T010141Z-sarosh-to-all-intelligence-api.md` (on `feat/sarosh/code-intelligence`)
