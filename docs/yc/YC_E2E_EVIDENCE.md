# YC end-to-end evidence — 2026-10-31

Rule: nothing here is production evidence unless the row says **PROD**. No assessment record was seeded,
hand-edited or fabricated. Unsupported steps are **NOT VERIFIED**.

## Target journey and status

| Step | Status | Evidence |
|---|---|---|
| 1. Frontend loads (`ari-ai-lake.vercel.app`) | PROD: up | `/api/frontend-version` 200, frontend `c03a5501` |
| 2. Backend reachable | **PROD: DOWN** | `/healthz` + `/readyz` → Railway 404 "Application not found"; frontend `backendReachable:false` (07:36Z, 07:42Z) |
| 3. GitHub sign-in | NOT VERIFIED | backend down |
| 4. Connect authorized test repository (GitHub App install) | NOT VERIFIED | backend down; no authorized test repo/App credentials in this session |
| 5. Push/PR webhook → per-commit assessment queued | NOT VERIFIED (prod) / VERIFIED (local, simulated webhooks) | `test_auto_commits.py`, `test_review_pipeline_reliability.py` on `71281707` |
| 6. Assessment runs, survives worker restart | VERIFIED (local real stack, scripted model) on `main 9437e217`; **partial** on `71281707` | `restart_recovery.py` below |
| 7. Findings + approval pause | VERIFIED (local, scripted model) | S1/S3 |
| 8. PR review comment posted exactly once | NOT VERIFIED (prod) / VERIFIED (local, fake GitHub client) | #693 suites |
| 9. Disconnect stops further writes | NOT VERIFIED (prod) / VERIFIED (local, threads + real Postgres, fake GitHub) | #694 suites + `test_review_post_disconnect_lease.py` |
| 10. Outage is detected and alerted | VERIFIED detection only (read-only against PROD) | `uptime_watch.py` exit 1, `healthz returned HTTP 404`; issue creation NOT VERIFIED |

**Full E2E status: NOT VERIFIED.** It requires a live backend and an authorized company-owned test repository
with the GitHub App installed. Re-run steps 2–9 after the runbook §2–§3 redeploy.

## Local real-stack runs

`deploy/evidence/restart_recovery.py`: embedded PostgreSQL 16 + Alembic + FastAPI + real `hackatl-worker`
subprocesses + durable queue + artifact store + local-dev sandbox; model replies are scripted (`provider_mode="fake"`).

### main `9437e217d65aa1be22fa7b4f54f723200cd428c8`

`uv run python deploy/evidence/restart_recovery.py --out /tmp/ari-evidence-main` → exit 0

```
S1_graceful_drain: PASS  (job succeeded, AWAITING_APPROVAL, checkpoint on disk, attempts 1)
S2_hard_kill_honest_failure: PASS  (FAILED, CONFLICT_STATE "cannot resume from RECON: paused orchestrator state was lost", attempts 2)
S3_checkpoint_resume: PASS  (COMPLETED after 2 approvals, 50 artifact objects)
S7_post_crash_new_assessment: PASS
S4_exactly_once_drain: PASS  (11/11 probe jobs, all attempts 1, 1 dedupe row)
S5_migration_rollback: PASS  (0017→0016→head)
S6_backup_restore: PASS  (row counts identical)
```

### integration `712817073f8a23d7f2fcfd550ca13eed66d99374` (main + #693 #694 #695 #723 #725)

`uv run python deploy/evidence/restart_recovery.py --out /tmp/ari-evidence` → exit 1

```
S1_graceful_drain: PASS
HARNESS_ERROR: FAIL  TimeoutError: poll timeout after 180s; last=AWAITING_APPROVAL
```

S2 SIGKILLs the worker mid-run and waits for FAILED. With #725 the assessment is restarted once and reaches
AWAITING_APPROVAL instead, so the harness times out and S3–S6 never ran on this tree. This is finding R1
(YC_BACKEND_READINESS.md): the harness must be updated to the new recovery semantics and re-run before this
row can be marked VERIFIED.

## Test suites

See YC_BACKEND_READINESS.md "Tests executed". Composed tree `71281707`: backend + security-agents + ops
**1907 passed, 32 skipped**, exit 0. Skips are opt-in live-provider/rehearsal tests; none were run.
