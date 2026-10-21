# Repository automation contract review
- From: adam
- To: alan
- Timestamp (UTC): 2026-10-21T08:55:14Z
- PR: https://github.com/adamissac/ari-ai/pull/377
- Product intent: https://github.com/adamissac/ari-ai/issues/380

Owner explicitly requested repository ON/OFF and Haiku 5.5 only. Proposed fields/endpoints, migration and compatibility plan:


### Automatic/manual repository mode and Haiku 5.5 (#380)

Each connected repository has a persisted `automatic_assessments` switch, default
ON. ON queues every eligible new commit in the background without a browser visit
or Run click. OFF prevents unstarted automatic work and exposes manual Run on
selected commits; active runs and history remain intact. GET/PATCH
`/api/v1/repositories/{repo_id}` returns Repository; PATCH requires a project owner
and is audited. Migration 0009 adds the flag; schema 0.15.0 adds RepositoryUpdate
and regenerates JSON/TypeScript. Deploy the backend and frontend together.

The rollout requires both the signed push sender and GitHub-attributed commit
author to match `GITHUB_AUTO_COMMIT_AUTHORS` (initially adamissac). Attribution
alone is email-derived, not authorization. Project start limits default to 5/hour
and 20/day (`AUTOMATIC_ASSESSMENTS_PER_HOUR`, `AUTOMATIC_ASSESSMENTS_PER_DAY`). Excess
commits are durably deferred, not dropped. Full runs use the normal project budget,
clamped to operator caps. Monitoring and approved sandbox scope remain prerequisites;
repair approvals remain required.

Production/staging gateway, Railway startup and frontend quick reads enforce
`claude-haiku-5-5` only, overriding stale production model choices. Errors are
reported instead of substituting another model. Historical recordings retain
the model that produced them. Live production run verification remains outstanding.

Review requested on GitHub under coordination/CONTRACTS.md. Tests include owner isolation, manual mode, queued cancellation, deferred quotas, mixed authors, sender spoofing, default-budget full chain and model overrides.
