# Pilot Final Readiness — Ari AI first-customer pilot

> **Status: DRAFT / checkpoint — current recommendation: NO-GO (pending).**
> Living document written by the pilot-completion-commander (Adam lane, Devin session
> `89af211994aa458d96ecf9f412c05bd7`). Each claim is labelled with how it was proven, and
> results reported by other agents are kept separate from ones re-run here.
> Last updated: 2026-10-25T01:35Z.

## 1. Versions under test

| Component | Version | How observed |
|---|---|---|
| `main` | `dc9a623a` (includes #530 `22454ef2`, #531 `ac87a290`, #567 `5a56e44c`) | `git fetch` 2026-10-25T01:10Z |
| Railway API `ari-ai-production-76d4.up.railway.app` | `git_sha=dc9a623a…`, `schema_version=0.22.0` | `GET /healthz` 01:10Z |
| Vercel frontend `ari-ai-lake.vercel.app` | landing page serves; deployed SHA not yet pinned | browser |
| DB migrations | single Alembic head `0017` (verified locally on `5a56e44c`) | `backend.migrate.alembic_config()` |

## 2. Binding pilot conditions

Legend: **PASS-local** = real code + real Postgres on a dev machine, scripted LLM ·
**PASS-prod** = observed on the deployed stack · **REPORTED** = another agent's evidence, not yet
re-run here · **OPEN** = not proven · **FAIL** = defect reproduced.

| # | Condition | Owner | Method | State |
|---|---|---|---|---|
| C1 | `main` boots, migrates, suite green | integration-lead | `make check`, `make test`, boot, curl | **PASS-local** on `5a56e44c`: 828 passed / 16 skipped / 0 failed (4m49s); ruff/format/contract checks pass; `/healthz` 200, `/readyz` 200, `/diagnostics` 401 unauth / 200 owner. **Re-verified PASS-local on `dc9a623a`: 832 passed / 16 skipped / 0 failed (313s)**, fresh DB migrated to single head `0017` |
| C2 | Prod API healthy on exact deployed SHA | integration-lead | `/healthz`, `/readyz` | **PASS-prod (readiness only)**: SHA matches; db/queue ok; 12 workers heartbeating; llm=live `claude-haiku-5-5`; GitHub App/OAuth/webhook configured; sandbox=vercel; artifact store writable. Readiness alone does not show that an assessment completes (see C4) |
| C3 | Prod queue drains | integration-lead | read-only prod DB (Adam-provided URL, `default_transaction_read_only=on`) 01:30Z | **Diagnosed — not stuck, but churning**: of 359 queued jobs, 354 are `assess_github_commit` with `run_after` in the future, all sharing one timestamp (01:30:28Z) and dedupe `github:deferred:<job>`. When that time arrives they all become due together, capacity admits ≤1, and the rest re-enqueue. That makes ~3–4k jobs/h (7,134 of 7,419 assess jobs in 2h were deferral re-enqueues); totals 16,211 succeeded, 56 failed, 0 dead. The backlog cannot drain at 5/h. Accepted pilot limitation; post-pilot fix is to collapse deferrals per repo to the newest SHA |
| C4 | Hosted customer journey (OAuth → connect → index → scope → manual assessment → 7 roles → validated planted vuln → fix → human approval → PR → independent verify → dashboard persistence) | pilot-completion-commander | Real browser on `ari-ai-lake.vercel.app` + `adamissac/pilot-rehearsal-target` | **OPEN — blocked on Adam's GitHub OAuth sign-in in the session browser**. Target repo: private, App installed, `main`=`256c8e8c` (Ari build-recipe PR #1 merged by `ari-security[bot]` 00:40Z). Webhook 202 at 00:07Z is not counted as evidence |
| C5 | Two-org isolation | rehearsal owner | `backend/tests/test_pilot_rehearsal.py` | **REPORTED PASS-local** (34 probes, uniform 404) in [REHEARSAL_REPORT](REHEARSAL_REPORT.md); test is in the 828-pass suite above. Prod two-org probe: **OPEN** |
| C6 | Secret redaction: code-intel index/context (`code_intelligence/privacy.py`) | integration-lead (fixing) | 17-case probe: leak / `ast.parse` / line count | **FAIL on main**: parse and line count preserved in 17/17, but the secret value survives in 10 classes: `*_token` names, bare `token`, Stripe `sk_live_`, `postgresql://u:p@`, JWT, Google `AIza`, paren-concat multiline, 2nd tuple element, `os.environ.get(..., default)`, digit-less mid-line kwarg |
| C7 | Secret redaction: `jobs.last_error` (`backend/redaction.py`) | integration-lead (fixing) | direct `redact_text` probe | **FAIL on main**: `postgresql+psycopg://admin:<pw>@…` not scrubbed; `access_token=`, `DB_PASSWORD=`, `client_secret:` not scrubbed |
| C8 | Dead-letter jobs endpoint authz | release-gate owner | code review | **PASS (code review)**: `require_project` → 404 for non-members; owners get redacted error, other members coarse code/category. **PASS-local runtime** on `dc9a623a`: owner 200 (dead+failed items), non-member 404 |
| C9 | `purge_project` deletion | rehearsal owner | `test_purge_project_deletes_every_surface` | **REPORTED PASS-local**; prod/faithful-disposable run: **OPEN** |
| C10 | #412 / #458 not merged | integration-lead | PR state | **PASS**: both open, held for human security review |
| C12 | Prod availability | Adam / integration-lead | `/healthz`, pg_stat_activity | **FAIL (in progress)**: 502 since ~01:27Z after main→`2c8ad50d` (#571); Railway check green; DB shows no API/worker connections; last heartbeat 01:26:51Z |
| C13 | Prod identity integrity | rehearsal owner / Adam | read-only DB | **OPEN — security flag**: synthetic users `rehearsal-alice`/`rehearsal-eve` created in prod 01:28:42Z; `rehearsal-alice` is **owner** of `org_01M55VPKH8T3P1WWEB73YQ8RDS` (adamissac personal, owns the rehearsal repo); no audit event for the grant. Both users have `github_id=NULL` and their own personal orgs; at 01:28:56Z alice's session made a real API call (`project.created` "Pilot Rehearsal (prod leg)"). The only code path that creates a user without OAuth is `POST /api/v1/auth/dev/login`, gated by `is_dev && auth_dev_login_enabled` (`backend/api/auth.py:89`). Either that gate is open in prod, or users, sessions and memberships were written straight to the DB (the missing membership audit event points to direct writes). Next check once prod is back: unauthenticated dev-login must return 403. Asked the rehearsal session 2c9458c9. If a non-OAuth prod login path exists → NO-GO |
| C14 | DB tenant enforcement | backend owner | read-only DB | **Finding**: the app role is `postgres` (`rolsuper`, `rolbypassrls` = true); RLS is enabled on 2/47 public tables, so tenant isolation is enforced only by the application layer (C5). **This violates `docs/security/TENANT_DATA_PROTECTION.md:160` ("production must not run the app as a superuser")**: migration 0016's FORCE RLS on `index_payloads`/`index_snapshots` is inert in prod. Owner action: create a NOSUPERUSER NOBYPASSRLS app role, set it as the app `DATABASE_URL`, keep `postgres` for migrations, and verify `/readyz` plus a tenant-GUC probe. Needs Adam, because it is a prod credential/role change. Local drill on `2c8ad50d` (embedded PG): superuser `postgres` saw 2/2 `index_payloads` rows with no GUC despite FORCE RLS. The NOSUPERUSER NOBYPASSRLS role saw 0 with no GUC and 1 per tenant GUC. **Confirmed: RLS gives no protection under the prod role.** |
| C15 | Storage | Adam / infra | read-only DB | DB 3,398 MB, of which `index_payloads` is 3,320 MB; retention policy for index payloads not yet verified |
| C16 | Redaction fix re-probe (pre-merge) | integration-lead | `~/ari-verify/r531/probe2.py` + `be_probe.py` against branch heads, 01:42Z | `fix/adam/redaction-gaps`@`8d51fc63`: intel 17/17 cases 0 leaks, parse ok, lines unchanged; backend: 4 original cases fixed, **3 new leaks** (quoted value with space, `Authorization: Bearer`, double-quoted `refresh_token`). `fix/adam/intel-redaction-gaps`@`a50ac500`: 2 intel leaks + backend untouched → superseded. Ruling: over-redaction policy accepted. **Still OPEN until merged + re-probed on main** |
| C17 | `purge_project` faithful disposable drill | commander (local) | `~/ari-verify/purge-drill/drill.py` on `2c8ad50d`, migrated to 0017 | **PASS (local, not prod)**: adversarial suite 17/17. Two orgs set up via API; after purge(A), A has 0 rows in all 39 project tables, B unchanged, A's artifact file removed and B's kept, 8 API reads 404 for A and 200 for B. Retained by design: orgs, users, memberships, sessions, audit events. Prod purge not exercised |
| C11 | Branch protection | Adam | GitHub settings | **Limitation**: not available on this personal private repo; human-reviewed merges by integration-lead ([BRANCH_PROTECTION_LIMITATION](BRANCH_PROTECTION_LIMITATION.md)) |

## 3. Code intelligence — reproduced on `5a56e44c` (code of #531)

Command: `PYTHONPATH=code-intelligence:shared .venv/bin/python code-intelligence/evidence/index_benchmark.py <repo> <sha> [prefix]`.
Local machine, single run, no LLM.

| Target | Files parsed | Imports | Routes | Call edges | Time | Py heap peak |
|---|---|---|---|---|---|---|
| `examples/payments-lite` | 9 | 52/52 | 8/8 | 198 | 0.25 s | 3.6 MB |
| `backend/` | 146 | 2549/2549 | 112/114 + 2 flagged | 9,594 | 5.1 s | 107 MB |
| whole repo | 533 | 8426/8426 | 137/139 + 2 flagged | 29,117 | 22.2 s | 494 MB |

Whole-repo call-edge resolution: **exact 7,747 (26.6%) · likely 580 (2.0%) · unresolved 20,790 (71.4%)**.
This is the same ~72% unresolved reported earlier, so the problem has not improved. Breakdown of the unresolved edges (heuristic classifier over `callee_name`):
attribute call on a local variable/expression 47.1%, stdlib/third-party module 20.1%,
builtin 18.9%, bare local/closure/imported name 11.6% (top: `Field`, `Path`, `client_factory`,
`timedelta`, `dataclass`), `self`/`cls` attribute 2.3%. About 39% (stdlib/3rd-party + builtins)
cannot resolve to repository symbols by design. The two non-literal routes (`FIXTURE_ROUTE`,
`CONTROL_PATH`) are now reported as index issues instead of being dropped silently. Retrieval recall
(82% payments-lite / 63% Ari, from #531's PR) has **not yet been re-run here**.

## 3b. Seven-agent pipeline and functional reviewer — scripted/replay evidence on `dc9a623a`

Every result in this section uses **scripted model turns (`provider_mode=fake`) with real tools**. None of it is live-provider or prod evidence.

- `security-agents` suite: **594 passed / 24 skipped / 0 failed** (skips: 11 Docker sandbox, 11 live opt-in, 2 import/compat). The first attempt in a fresh venv failed with `No module named 'yaml'`; it passed after `pyyaml` was installed. `security_agents/intel/labels.py` imports `yaml` lazily, but `security-agents/pyproject.toml` does not declare it. The workspace gets it only through `hackatl-code-review`, so the workspace/prod install is fine and the standalone README install breaks (minor; doc/dependency fix).
- Replay `security_agents.cli --target ../examples/payments-lite --auto-approve`: Scout, Probe, Trace, Diagnose, Fortify, Patch and Verify all `succeeded`; final finding `hardened`.
- `code-review` suite: **90 passed / 4 skipped**; `code_review.eval_corpus`: 10/10 labels `ok`. The corpus is the tuned fixture set. It is **not** an independent held-out evaluation, so it says nothing about real-world reviewer accuracy (still **OPEN**).
- Tests that cover each failure mode: invalid structured output (retried once, then the step fails), provider outage → `LLM_UNAVAILABLE`, retries, inconclusive Probe, false positive refuted by executed evidence, ineffective/out-of-plan/test-weakening patches rejected, Verify rejecting bad patches, cancellation, token/USD/turn budgets, and honest `unresolved` final states. **Gap: no test for a provider timeout specifically.** None of these failure modes has been exercised against the live provider.
- Live seven-role evidence (REPORTED, not re-run here): all roles live on `examples/inventory-lite`, planted IDOR confirmed and hardened, $0.0334 (#555).

## 4. Open human-only actions

1. **Adam**: complete GitHub OAuth in the session browser on `ari-ai-lake.vercel.app` (needed for C4, and for owner `/diagnostics` to settle C3).
2. **Adam**: give the operator read access to the prod queue (owner diagnostics or Railway DB read-only), or inspect it yourself: `SELECT kind, status, run_after > now() AS deferred, count(*) FROM jobs WHERE status='queued' GROUP BY 1,2,3;` (read-only).
3. **Adam**: separate human security review before #412/#458.

## 5. Recommendation

**NO-GO (pending)**. C4 (hosted journey) and C6/C7 (redaction FAIL on main) block a GO.
C3 must be settled. When those pass, the expected outcome is a CONDITIONAL GO, with C11 and the
code-intelligence limitations in §3 as accepted limitations.

## Appendix R — Owner runbook: non-superuser app role (C14)

Status: **proposed, not executed.** Prod change, so it needs Adam's approval, a fresh Railway backup and a maintenance window.
Facts it relies on (verified on `origin/main` 2c8ad50d): `deploy/railway/start.sh` runs `hackatl-migrate` (`backend.cli:migrate`) at boot with the
same `DATABASE_URL` as the API and workers. No separate migration URL setting exists. No migration uses `CREATE EXTENSION`, `CREATE ROLE` or other
superuser-only DDL. Tenant scoping uses `set_config('ari.project_id', …, true)` (transaction-local). FORCE RLS (migration 0016) also binds the table
**owner**, but never a superuser or a BYPASSRLS role.

Plan: make the app role the owner of the public schema objects, with `NOSUPERUSER NOBYPASSRLS`. Migrations keep working (an owner can run DDL),
and FORCE RLS then applies to it.

```sql
-- 0. Railway: take a manual backup first; record alembic version (expect 0017).
-- 1. As postgres:
CREATE ROLE ari_app LOGIN PASSWORD '<generate in Railway, never paste in chat>'
  NOSUPERUSER NOBYPASSRLS NOCREATEROLE NOCREATEDB;
GRANT CONNECT ON DATABASE railway TO ari_app;
ALTER SCHEMA public OWNER TO ari_app;
DO $$ DECLARE r record; BEGIN
  FOR r IN SELECT tablename FROM pg_tables WHERE schemaname='public' LOOP
    EXECUTE format('ALTER TABLE public.%I OWNER TO ari_app', r.tablename); END LOOP;
  FOR r IN SELECT sequencename FROM pg_sequences WHERE schemaname='public' LOOP
    EXECUTE format('ALTER SEQUENCE public.%I OWNER TO ari_app', r.sequencename); END LOOP;
END $$;
-- 2. Railway service env: point DATABASE_URL at ari_app (same host/db); redeploy.
-- 3. Verify (read-only, as ari_app):
SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user;   -- f, f
SELECT count(*) FROM index_payloads;                                         -- 0 without GUC
BEGIN; SELECT set_config('ari.project_id','<rehearsal project id>',true);
SELECT count(*) FROM index_payloads; COMMIT;                                 -- that project's rows only
-- then /readyz workers alive, and one hosted assessment end-to-end.
-- Rollback: set DATABASE_URL back to the postgres URL and redeploy (ownership change is harmless to postgres).
-- 4. Rotate the postgres password (it was exposed in chat 2026-10-25).
```

## Appendix O — Prod outage 2026-10-25 (in progress)

- Postgres service log (pasted by Adam): the container restarted, "shut down at 01:26:51 UTC", "ready to accept connections" 01:26:54. `pg_postmaster_start_time()` = 01:26:54.
  The last worker heartbeat was 01:26:51.369Z. Since then: no API or worker connections in `pg_stat_activity`, and `/healthz` + `/readyz` return 502.
  Working hypothesis (not yet confirmed; API service logs needed): the API and workers did not survive the DB restart and are not being restarted by Railway.
- The same log shows **non-read-only activity against prod by an unidentified actor** (not this lane, whose connections are `default_transaction_read_only`):
  01:28:33 `insert into index_payloads (... 'prj_X' ...)` → permission denied; `drop role ari_rls_probe` → failed (dependent schema privileges).
  The role no longer exists, and no `prj_X` rows remain. `rehearsal-alice`/`rehearsal-eve` (github_id NULL) were inserted at 01:28:42, probably by the same actor
  writing directly to the DB rather than through an auth bypass. Not confirmed. No cleanup without Adam's approval.
- Railway SSH sessions to the Postgres container at 01:40:50 and 01:41:13 (actor unknown).
- 01:52:48Z: prod recovered on `580d2f67` (#532 merge deploy). `/readyz` ready, 12 workers, live LLM (`claude-haiku-5-5`).
- C13 update: the only `github_id IS NULL` users in prod (7 users total) are `rehearsal-alice`/`rehearsal-eve`, created 01:28:42 while the prod API was returning 502.
  They therefore came from a non-prod API process connected to the prod DB (consistent with `scripts/rehearsal/run_rehearsal.py`, which uses
  `/auth/dev/login`, plus `test_tenant_isolation_adversarial.py`'s `ari_rls_probe` role), not from the prod dev-login endpoint. No Devin session in the org matches; the source is
  being confirmed with Adam. Remaining action: Adam-approved cleanup of the 2 users, their sessions, memberships and project; then rotate the DB password.
- #570 redaction fix merged as `2c825c4e`: re-probe on main 18/18 intel + 7/7 `redact_text` PASS. Prod deploy of that SHA still to be checked.
- Governance: merge commits `4fdcad95` (#538) and `e44d27d7` (#536), plus squash `0272616e` (#540, authored by `devin-ai-integration[bot]`), carry
  `Co-Authored-By: Devin AI` trailers on main, which violates `human-only-git-attribution`. Rewriting history needs a force-push to main (owner decision; not done).
