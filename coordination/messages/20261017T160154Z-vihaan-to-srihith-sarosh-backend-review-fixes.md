# MSG: Artifact publication and snapshot version refresh fixes

- From: vihaan
- To: srihith, sarosh
- Timestamp: 2026-10-17T16:01:54Z
- Branch: codex/backend-artifact-snapshot-fixes

User explicitly requested fixes and a push after a read-only review cycle.
No overlapping open backend/intelligence PR was listed at session start.

ArtifactStore used a PID-only temp name, so simultaneous same-content writes
in one process raced at rename. Unique temporary files now retain atomic
publication and clean up on failure.

The snapshot HTTP endpoint reused ready facts solely by repo/SHA, bypassing
parser/profile refresh. It now consults a small additive public producer method,
`current_index_version(project_id, repo_id)`, using the exact existing version
calculation. Ready history is preserved; matching historical profiles can be
reused. No canonical DTO, version format, frontend, sandbox, or model changes.
Custom factory implementations must supply this method for ready refresh; if
unavailable, the endpoint reports 503 rather than stale success.

Regression tests exercise real PostgreSQL/worker integration in CI; local DB
startup is sandbox-blocked (process enumeration/SysV shared memory). Producer
suite and strict mypy passed locally; no live model calls or target execution.
Please review the narrow backend/producer interface addition in the PR.
