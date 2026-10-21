# Automatic commit scheduling
- From: adam
- To: all
- Kind: implementation-handoff
- Timestamp (UTC): 2026-10-21T04:41:00Z
- Branch: `feat/adam/automatic-commits`
- Scope: backend queue, GitHub identity reads, scope activation; no shared contract changes.

User requested automatic reviewer/seven-agent runs on each commit, initially only commits authored by GitHub account `adamissac`. Existing monitoring skips docs-only pushes, assesses only the final SHA, and coalesces requests without a rescheduler. Added opt-in per-commit queue with GitHub API author verification, repo/commit dedupe, full assessments, and scope-approval resume. Railway entrypoint defaults the rollout to adamissac. Existing monitoring remains when rollout config is empty. Explicit repository authorization, repair approvals, project budgets and operator caps remain enforced.

Validation so far: 16 focused tests passed, including signed push through full reviewer + seven-agent + approval + verification flow against PostgreSQL with scripted model responses and owned local sandbox. Broader tests and production verification pending. Live readyz is reachable but does not prove a paid provider run. No claims of live success.
