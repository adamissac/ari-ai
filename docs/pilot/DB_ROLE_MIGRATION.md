# Production DB: least-privilege app role, credential rotation, rehearsal cleanup

Status: **PLAN, NOT EXECUTED.** It needs owner approval before any step runs.
Nothing here is to be performed by an agent.

## Current state (read-only checks, 2026-10-25)

- `pg_roles` contains only `postgres` (`rolsuper=t`, `rolbypassrls=t`). All
  16 app connections (`pg_stat_activity`) authenticate as `postgres`.
- All 47 public tables are owned by `postgres`. `index_payloads` and
  `index_snapshots` have `ENABLE` + `FORCE ROW LEVEL SECURITY`. Superusers
  bypass both, so RLS is **inert for the app today**.
- `deploy/railway/start.sh` runs `hackatl-migrate` with the app's
  `DATABASE_URL`. A separate `MIGRATION_DATABASE_URL` is being added in a
  reviewed PR. This plan depends on that PR being merged and deployed first.

## Order (each step gated on the previous one passing)

0. **Backup.** Railway → Postgres → *Backups* → create a manual backup.
   Verify it by restoring into a scratch service or environment and checking
   that `alembic` head = 0017 and the row counts of `projects`, `assessments`
   and `index_payloads` match production. Do not continue without a verified
   restore.
1. **Create the role** as `postgres`, using a password generated in a
   password manager. The password is never pasted into chat or into files.
   ```sql
   CREATE ROLE ari_app LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE PASSWORD '<generated>';
   GRANT CONNECT ON DATABASE railway TO ari_app;
   GRANT USAGE ON SCHEMA public TO ari_app;
   GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO ari_app;
   GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO ari_app;
   ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO ari_app;
   ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO ari_app;
   ```
   Creating the role changes nothing for the running app.
2. **Pre-cutover probe as `ari_app`:**
   - `SELECT count(*) FROM index_payloads` with no tenant GUC → 0 rows.
   - The same query inside a transaction after `SELECT set_config('ari.project_id', '<real project>', true)` → that project's rows only.
3. **Cutover.** Railway → Agent service → *Variables*:
   - `MIGRATION_DATABASE_URL` = reference `${{Postgres.DATABASE_URL}}`
     (stays `postgres`).
   - `DATABASE_URL` = `ari_app` on the private host
     `postgres.railway.internal:5432/railway`.

   Then deploy. Effect on running work: the service restarts. Running jobs
   are re-claimed when their lease expires. Assessments *paused* for approval
   lose orchestrator state and fail honestly (REHEARSAL_REPORT D2), so cut
   over when no assessment is paused.
4. **Verify:**
   - `/readyz` returns 200.
   - `pg_stat_activity` shows app connections as `ari_app`.
   - An index + assessment on the rehearsal repo completes, which proves the
     GUC path works under RLS.
   - Re-run the 34-probe cross-org drill: 404s expected.
   - Repeat step 2's probe.
5. **Rollback** (if step 4 fails): set `DATABASE_URL` back to the
   `${{Postgres.DATABASE_URL}}` reference and redeploy. The unused role is
   harmless; drop it later.
6. **Credential rotation** (only after step 4 passes):
   - **Postgres:** rotate the `postgres` password using Railway's Postgres
     credential procedure, then confirm that the reference variables
     resolved to the new value (`/readyz` 200, migrations run on deploy).
     Then Postgres → *Settings* → *Networking* → remove public access. After
     this, operator access goes through `railway connect Postgres`.
   - **Anthropic:** console → API keys → create a new key, set
     `ANTHROPIC_API_KEY` on the Agent service and deploy. Once `/readyz`
     reports `llm.configured` and a live run succeeds, disable the old key.
   - **GitHub App:** App settings → *Private keys* → generate a new key and
     update the Railway variable, then deploy. Once a webhook delivery and an
     installation-token fetch succeed, delete the old key.

## Rehearsal cleanup (for approval; runs only after the C9 re-run)

Inventory (read-only query, 2026-10-25):

| Object | IDs | Proposed handling |
|---|---|---|
| Users | `usr_A40D640D9695D19372BACD36EB` (rehearsal-alice), `usr_7C13AB87FA6E020B936382C9C7` (rehearsal-eve); `github_id` NULL | Retain rows (audit references). After the steps below they have no access |
| Sessions | 1 per user, expire 2026-11-01 | `POST /api/v1/auth/logout` with each session (supported mechanism) |
| Membership in owner org | alice → `org_01M55VPKH8T3P1WWEB73YQ8RDS` (owner) | No API exists. One approved single-row SQL delete (`org_id`+`user_id` match) |
| Personal orgs | `org_4893E29D9B9FDCD265ACD26992`, `org_C992A0C6A94705736F4C7E61AC` | Retain |
| Project | `prj_01M5RASMAA4GT4EDKWJMCQGAWF` (alice org, no repos indexed) | `purge_project` (operator runbook, supported) |
| Assessments | `asm_01M5RCNXY6CTM8S8S3MDQ6ZFBD`, `asm_01M5RCVC20ZMYH8EKTZQP40W73`, `asm_01M5RD308T0RER91FNMQ0JGP0Q`, `asm_01M5RD406NQC4GRRT48N64ANNY` (owner project) | Retain as rehearsal evidence |
| Scope | `scp_01M5RD3YN9JH9V652ATKS93GKV` (revoked) | Retain (audit) |

Evidence is kept on the operator machine (report JSON, patch and
verification artifacts, probe logs) before any cleanup.
