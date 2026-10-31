# YC deployment runbook — Railway backend + Vercel frontend

Scope: restore and verify production after an outage, and roll forward/back. Every step that changes a live
deployment must be run by an operator with Railway/Vercel project access (Alan or Adam). Devin sessions have
no production credentials and must not perform these steps. Do not paste secret values into issues, PRs or chat.

## 1. Detect

| Signal | Healthy | Down (observed 2026-10-31 07:36Z / 07:42Z) |
|---|---|---|
| `curl -s -w '%{http_code}' https://ari-ai-production-76d4.up.railway.app/healthz` | `200 {"status":"ok",...,"git_sha":...}` | `404 {"status":"error","code":404,"message":"Application not found"}` |
| `curl -s -w '%{http_code}' https://ari-ai-production-76d4.up.railway.app/readyz` | `200`, `db/queue ok`, workers alive | same Railway 404 |
| `curl -s https://ari-ai-lake.vercel.app/api/frontend-version` | `backendReachable:true`, `sameCommit:true` | `backend:null, backendReachable:false, status:"unknown"` |
| `uptime-watch` workflow (after #723 merges) | green run, no open `[ops-alert] Production is down` issue | red run + issue |

Read-only local check (no tokens needed for the HTTP part):
`uv run python scripts/ops/uptime_watch.py` (on a tree containing #723) → exit 1 and the problem list when down.

`/healthz` is static (no DB). Always also check `/readyz`: it returns 503 when the DB, queue or required workers
are unavailable, and its `capabilities` block shows LLM/GitHub App/sandbox/artifact-store configuration.

## 2. Restore (operator)

Railway's 404 "Application not found" means no live deployment is serving the domain — not an app error.

1. Railway → project → environment `production`. For **Postgres** and **ari-ai** check *Deployments*:
   is there a latest deployment, and is it `SUCCESS`? Note what removed the deployment (activity log) for the
   incident record — the root cause of the 10-28 and 10-31 removals is still unknown.
2. **Postgres first.** If its deployment is gone, redeploy it (service → Deployments → Redeploy) and confirm the
   volume `postgres-volume` is still attached and not re-created. If the volume is empty/new, stop: restore from
   the newest Railway backup (Volumes/Backups) before starting the app — `hackatl-migrate` on an empty DB would
   create a fresh schema and the app would look healthy with no data.
3. **ari-ai service.** Redeploy the latest successful deployment of the intended `main` SHA (or *Deploy* from
   `main`). Do not deploy a PR branch. Variables are listed in `docs/deploy/RAILWAY_AND_GITHUB_APP.md` §2;
   verify they exist (names only) — `DATABASE_URL` must reference the Postgres service.
4. Startup order is enforced by `deploy/railway/start.sh`: `hackatl-preflight --config --worker` (fails fast on
   missing secrets/dev settings) → `hackatl-migrate` (Alembic to head) → 12 `hackatl-worker` + `hackatl-api` →
   `python -m backend.redeliver` (asks GitHub to redeliver webhooks missed while down) → maintenance sidecar.
   A failing preflight or migration exits the container; read the deploy logs, do not bypass.
5. Vercel needs no action unless `BACKEND_ORIGIN` changed.

## 3. Verify (no false readiness claims)

Run all of these; record outputs (without secrets) in the incident issue:

1. `/healthz` → 200 and `git_sha` equals the intended `main` SHA.
2. `/readyz` → 200, workers `alive > 0`, `capabilities_ready:true`. `ready` with `capabilities_ready:false` means
   the service is up but **cannot run a real assessment** — not ready for a demo.
3. `/api/frontend-version` → `backendReachable:true`, `sameCommit:true`.
4. `uv run python deploy/release_check.py --base-url https://ari-ai-production-76d4.up.railway.app --ops-token "$OPS_TOKEN" --strict`
   (token from the operator's environment; every row PASS; WARN/SKIP block under `--strict`).
5. Signed-in owner: `GET /diagnostics` — migration head matches code, GitHub App JWT check OK.
6. One assessment on an **authorized company-owned test repository** reaches `AWAITING_APPROVAL` or `COMPLETED`
   with real findings (never seed or hand-edit assessment rows). Without this, report the deploy as
   "up, assessment path NOT VERIFIED".
7. After #723 merges: Actions → uptime-watch → *Run workflow* → green, and any open `[ops-alert] Production is down`
   issue gets the recovery report and closes.

## 4. Roll back

- App: Railway → ari-ai → Deployments → previous `SUCCESS` deployment → *Redeploy*. Migrations are forward-only in
  production; a rollback across a migration needs `hackatl-migrate` downgrade validated on a scratch DB first
  (`deploy/evidence/restart_recovery.py` S5 exercises 0017→0016→head locally).
- Data: `deploy/scripts/db_backup.sh` / `db_restore.sh`; restore to a **scratch** Postgres first and compare
  `SELECT count(*)` on `assessments`, `findings`, `audit_events` (docs/deploy/POSTGRES_STORAGE.md).

## 5. Monitoring that must exist before the pilot

| Monitor | Where | State on `main` 9437e217 |
|---|---|---|
| Storage/backup age | `storage-watch.yml` (hourly) | present |
| Deployment existence + `/healthz` | `uptime-watch.yml` (15 min) — #723 | **not merged** |
| DB/worker readiness probe | should be `/readyz` (finding W1 on #723) | missing |
| Missing `RAILWAY_TOKEN` surfaced as a problem | finding W2 on #723 | missing |
| In-app alerts | `ALERT_WEBHOOK_URL`, `OPS_ALERT_WEBHOOK_URL` | configured? NOT VERIFIED |

The watchdog only alerts; there is no automatic redeploy. Mean time to recover = time to notice the issue/email
+ an operator with Railway access.

## 6. Merge order for the reliability PRs (owners merge; Devin does not)

#693 → #694 (contains #693 + the review-POST lease reconciliation) → #725 → #723 → #695. After #694, the others
conflict only in `CHANGELOG.md`/`docs/planning/SESSION_HANDOFF.md` (union both sides). Re-run the full suites on
`main` after each merge; then redeploy per §2–§3.
