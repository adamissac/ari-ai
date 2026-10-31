# YC backend readiness — 2026-10-31

Owner lane: backend reliability and infrastructure (Devin). Frontend/demo UX: Claude. Release approval: Codex.
Nothing in this file closes a finding; Codex decides. Status words: **VERIFIED (local)** = executed in this
session on the named SHA against the embedded Postgres stack; **NOT VERIFIED** = not executed, or not executable
without access this session did not have.

## Verdict: NO-GO for the demo / first-customer pilot

1. **Production is down.** `GET https://ari-ai-production-76d4.up.railway.app/healthz` and `/readyz` return
   Railway `404 "Application not found"` (observed 2026-10-31 07:36Z and 07:42Z); the Vercel frontend reports
   `backendReachable:false`. Same signature as the 2026-10-28 incident. Needs a Railway redeploy by someone with
   project access (runbook §2). This session has no Railway credentials and deployed nothing.
2. The five reliability PRs are open, none merged. Composed together they pass the local suites (below), but
   they are not on `main`, so production (once redeployed from `main`) still lacks every fix here.
3. One harness expectation conflicts with #725 (finding R1). Codex has not audited the composed tree.

## Canonical state

- `adamissac/ari-ai` `main` = `9437e217d65aa1be22fa7b4f54f723200cd428c8`.
- Composed integration tree (not a PR, for audit only): `m-alan08/ari-ai` branch `devin/1793447000-yc-integration`
  = `c9eedf7a9827e66095b126a6a52fcc64dd8af519` = main + #693 + #694 + #695 + #723 + #725 (merge order) + the
  #693×#694 regression test + the P2 fix below. (Previous audited head: `71281707`.)

| PR | Lane | Head SHA | Conflicts with main/others |
|---|---|---|---|
| [#693](https://github.com/adamissac/ari-ai/pull/693) review pipeline reliability | review delivery | `c3d5e552` | code conflict with #694 in `auto_commits.post_pr_review` |
| [#694](https://github.com/adamissac/ari-ai/pull/694) disconnect / write safety | disconnect | `32dc528d` (updated this session; now contains #693 + P2 fix) | resolved — merge #693 first or #694 alone |
| [#695](https://github.com/adamissac/ari-ai/pull/695) staging pilot / release signoff | deploy gates | `9cbacc3e` | CHANGELOG, SESSION_HANDOFF only |
| [#723](https://github.com/adamissac/ari-ai/pull/723) production uptime watchdog (Adam) | monitoring | `56204e4a` | CHANGELOG only |
| [#725](https://github.com/adamissac/ari-ai/pull/725) assessment lost-state recovery (Adam) | lifecycle | `79067534` | CHANGELOG only |

## Original production issues → root cause → change

| # | Issue | Confirmed root cause | Change | Status |
|---|---|---|---|---|
| P1 | 2026-10-28 outage: Railway app + Postgres deployments removed, app 404 until 10-30; nothing alerted | Only `storage-watch.yml` existed; it reads volume usage/backups, not deployment existence or HTTP health | #723 `scripts/ops/uptime_watch.py` + `uptime-watch.yml` (every 15 min, dedup'd `[ops-alert] Production is down` issue, exit 1) | Detection VERIFIED (local, read-only): run against prod today prints `healthz returned HTTP 404`, exit 1. Scheduled run, `RAILWAY_TOKEN` secret, issue creation: NOT VERIFIED (not on main) |
| P1b | Prod down again 2026-10-31 | NOT VERIFIED (no Railway access; cause unknown) | none — needs operator | open |
| R-dup | Duplicate / lost PR reviews on redelivery, retries, 5xx | Non-atomic ownership; 5xx assumed "not created" | #693 effect reservation + hidden marker read-back, `recovery_required` on unknown outcome | VERIFIED (local) by #693 suites on composed tree |
| R-rate | GitHub rate limits burned retry attempts | errors treated as failures | #693 `JobDeferred` | VERIFIED (local) |
| D-race | Write after disconnect returned 200 | Re-check outside a lease; token mint/push/PR/review not fenced | #694 `connection_guard.github_write` advisory lease, disconnect takes it (409 if stuck) | VERIFIED (local) |
| D×R | With #693 alone, disconnect could return 200 while the review POST was on the wire (#693 scorecard residual) | #693's row lock is released before the POST | this session: `post_pr_review` runs `ctx.effect(...)` + POST inside `github_write` (pushed to #694) | Reproduced: `test_review_post_disconnect_lease.py` FAILS with the lease replaced by a no-op (`disconnect:200` while POST in flight), PASSES with it |
| A-lost | Worker crash → assessment FAILED "paused orchestrator state was lost" with no recovery | no restart path for lost orchestrator state | #725 `restart_lost_state`: one automatic restart to SCOPE_CHECK with usage carried forward, then FAILED `CONFLICT_STATE`; budget exhaustion honoured; FAILED always carries an error | VERIFIED (local) by #725 tests; see R1 |

## Tests executed (exact commands, this session)

All on the local embedded Postgres stack; FakeLLM/scripted transports where tests use them. Not production evidence.

| Tree | Command | Result |
|---|---|---|
| main `9437e217` | `uv run pytest -q -x -p no:cacheprovider backend/tests` | **879 passed, 9 skipped**, exit 0 |
| main `9437e217` | `uv run python deploy/evidence/restart_recovery.py --out /tmp/ari-evidence-main` | S1–S7 all PASS, exit 0 |
| integ `71281707` | `make check` ; `uv run mypy` | pass ; `Success: no issues found in 41 source files` |
| integ `71281707` | `uv run pytest -q -p no:cacheprovider backend/tests security-agents/tests tests/ops` | **1907 passed, 32 skipped**, exit 0 (12m14s) |
| integ `facd76fc` (before the test commit) | targeted: review_pipeline_reliability, pr_review_effect_ownership, security_audit_disconnect_writes, disconnect_write_token_ordering, auto_commits, auto_delivery, assessment_restart, e2e_host, staging_pilot, release_signoff_binding, parallel_migrations | **270 passed**, exit 0 |
| integ `71281707` | `uv run python deploy/evidence/restart_recovery.py --out /tmp/ari-evidence` | S1 PASS; **S2 FAIL** (`poll timeout after 180s; last=AWAITING_APPROVAL`) → finding R1 |
| #694 `ff047025` | targeted: review_pipeline_reliability, pr_review_effect_ownership, security_audit_disconnect_writes, disconnect_write_token_ordering, review_post_disconnect_lease, auto_commits, auto_delivery, redaction_literal_forms | **224 passed**, exit 0 (`4e35c397` adds a CHANGELOG-only commit) |
| #694 `4e35c397`  | `uv run pytest -q -p no:cacheprovider backend/tests` | **950 passed, 9 skipped**, exit 0 |
| #694 `32dc528d` (P2 fix) | `uv run pytest -q -p no:cacheprovider backend/tests/test_pr_review_effect_ownership.py` before the fix | new P2 test **fails** (`assert 2 == 1`: two accepted POSTs) |
| #694 `32dc528d` (final head) | targeted review/disconnect/auto_commits files; then `uv run pytest -q -p no:cacheprovider backend/tests` | **157 passed**; **950 passed, 9 skipped**, exit 0 |
| integ `c9eedf7a` | targeted review/disconnect/auto_commits/auto_delivery files | **209 passed**, exit 0 |
| #723 `56204e4a` | `python -m unittest tests/ops/test_uptime_watch.py -v` (py3.12) | 8 passed |
| prod (read-only) | `python scripts/ops/uptime_watch.py` without tokens | reports `healthz returned HTTP 404`, exit 1 |

Skipped tests are opt-in live tests (`RUN_LIVE_LLM_EVAL`, `REHEARSAL_LIVE`) or missing optional `rl_defense`; none ran.
GitHub CI for #693 and #723 could not be read (provider API rate limit) — NOT VERIFIED, not "failed".

## Fixed after Codex review (P2, duplicate review)

- **P2 (Codex): an accepted review POST that answers 5xx could be posted twice.** `post_pr_review` read the PR's
  reviews back right after the 5xx and treated "marker not found" as proof of non-application, so the job retried.
  GitHub reads can lag the write, so a review that was created could be posted a second time. Codex's fake-provider
  probe showed two accepted POSTs for one effect.
- Fix (#694 `32dc528d`, `backend/backend/auto_commits.py`): after a 5xx, only a found marker settles the effect as
  posted. Not found, or a failed lookup, now ends the job `recovery_required` with no automatic retry. An operator
  resolves it through the existing `resolve_recovery` path (`applied` / `not_applied` / `retry`).
- Regression test: `test_accepted_post_with_503_and_lagging_read_back_is_not_reposted` in
  `backend/tests/test_pr_review_effect_ownership.py`. It replaces `test_http_500_confirmed_absent_on_github_is_retried`,
  which encoded the unsafe behaviour. It fails before the fix (2 POSTs) and passes after it.
- Trade-off: a 503 where GitHub really did not create the review now waits for an operator instead of retrying
  itself. A missing review can be recovered; a duplicate posted to a customer's PR cannot be taken back.

## Findings routed to owners (not fixed here)

- **R1 (#725, Adam) — evidence harness contradicts the new recovery semantics.** `deploy/evidence/restart_recovery.py`
  S2 SIGKILLs a worker mid-assessment and waits for `FAILED/CONFLICT_STATE`. With #725 the assessment restarts once
  and reaches `AWAITING_APPROVAL`, so S2 times out and S3–S6 never run (S7's comment also assumes S2 is FAILED).
  The product behaviour looks intended; the harness (and RELEASE_CHECKLIST evidence that cites it) needs updating
  to assert: one `assessment.lost_worker_recovery` audit row, `automatic_restart=true` event, carried-forward
  `sandbox_seconds`, and a second kill → `FAILED` with `CONFLICT_STATE`. Until then the restart-recovery
  evidence on the composed tree is incomplete.
- **R2 (#725)** lost-segment estimate is capped at `worker_lease_s`; with renewable leases a long lost segment is
  under-counted toward budget (already noted in the PR). Accept or fix before customer budgets matter.
- **W1 (#723)** watchdog probes `/healthz`, which is static (no DB). Postgres down with the app container up
  passes the HTTP check; it is only caught if Railway marks the Postgres deployment non-SUCCESS. `/readyz` returns
  503 when DB/queue/required workers are down — probe it (or both).
- **W2 (#723)** without `RAILWAY_TOKEN` the deployment check is silently skipped (no "unchecked" problem line),
  so a missing secret degrades the watchdog to the HTTP probe without saying so.
- **W3 (#723)** watchdog only alerts; it never redeploys. Detection-to-recovery still depends on a human with
  Railway access (runbook §2).

## Remaining critical blockers

1. Production redeploy + post-deploy verification (operator with Railway access).
2. Merge order decision and merges by owners: #693 → #694 → #725 → #723 → #695 (CHANGELOG-only conflicts after #694).
3. R1 harness update, then re-run `restart_recovery.py` on the composed tree.
4. `RAILWAY_TOKEN` Actions secret present and `uptime-watch` producing a green run after #723 merges — NOT VERIFIED.
5. Codex audit of `c9eedf7a` / #694 `32dc528d` (or of `main` after merges), including the P2 fix.
6. Real end-to-end journey on an authorized test repository against a live deployment — NOT VERIFIED (see YC_E2E_EVIDENCE.md).
