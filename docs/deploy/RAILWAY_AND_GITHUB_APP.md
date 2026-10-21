# Hosting the real platform: Railway backend + GitHub App

The frontend runs on Vercel (`ari-ai`, https://ari-ai-lake.vercel.app). The control plane
(API, worker, migrations) runs as one Railway service built from `backend/Dockerfile` with
start command `railway-start` (`deploy/railway/start.sh`), a Postgres service and a volume
at `/data` (artifacts, repository checkouts). Secrets are entered in the dashboards by a
person, never committed and never pasted into chat.

## 1. Create the GitHub App (github.com → Settings → Developer settings → GitHub Apps → New)

| Field | Value |
|---|---|
| Name | e.g. `Ari AI` (must be unique on GitHub) |
| Homepage URL | `https://ari-ai-lake.vercel.app` |
| Callback URL | `https://ari-ai-lake.vercel.app/api/v1/auth/github/callback` |
| Request user authorization (OAuth) during installation | on |
| Setup URL | `https://ari-ai-lake.vercel.app/projects` (redirect on update: on) |
| Webhook URL | `https://ari-ai-production-76d4.up.railway.app/api/v1/webhooks/github` |
| Webhook secret | a long random string (also goes into Railway, below) |
| Repository permissions | Contents: **Read-only**, Metadata: **Read-only** |
| Subscribe to events | Push |
| Where can it be installed | Any account (so other people can use it) |

After creating it: note the **App ID** and **Client ID**, generate a **client secret**, and
generate a **private key** (downloads a `.pem`).

## 2. Railway variables (project → `ari-ai` service → Variables)

| Variable | Value |
|---|---|
| `GITHUB_APP_ID` | App ID |
| `GITHUB_APP_PRIVATE_KEY` | contents of the `.pem` (multi-line paste is fine) |
| `GITHUB_OAUTH_CLIENT_ID` | the App's Client ID |
| `GITHUB_OAUTH_CLIENT_SECRET` | the App's client secret |
| `GITHUB_WEBHOOK_SECRET` | the webhook secret from step 1 |
| `ANTHROPIC_API_KEY` | your key (set a monthly spend limit in the Anthropic console) |

Already set (non-secret): `DATABASE_URL` (reference to Postgres), `APP_ENV=production`,
`ARTIFACT_STORE_URI=file:///data/artifacts`, `SECURITY_WORKDIR=/data/work`,
`API_BASE_URL` and `FRONTEND_ORIGIN` = the Vercel URL, `RAILWAY_RUN_UID=0` (volume access).

## 3. Vercel (project `ari-ai`)

- `BACKEND_ORIGIN=https://ari-ai-production-76d4.up.railway.app`, and remove
  `NEXT_PUBLIC_DEMO_ONLY` so `/projects` is the real console again.
- Settings → Deployment Protection: turn Vercel Authentication **off** if people outside
  your Vercel team should be able to sign in.

## What runs where

Attacks never run on Railway. The worker fetches the selected repository at the exact
commit with a short-lived, read-only installation token, and executes it only inside a
throwaway Vercel Sandbox microVM (see `security-agents` Vercel Sandbox driver).

### Per-commit automatic assessments

The Railway entrypoint defaults `GITHUB_AUTO_COMMIT_AUTHORS` to `adamissac` when
unset. Set a comma-separated list of GitHub logins to expand the rollout, or `*`
for all GitHub-linked authors. Explicit empty uses the legacy impact/coalescing
policy. The allowlist requires both the signed sender and GitHub commit-author attribution.
An installed App, connected repository, enabled monitoring and approved repository
scope remain prerequisites. Approving a scope wakes blocked automatic commits.
Opening the commit page is unnecessary; it polls the persisted run when visited.
Check worker logs for `assess_github_commit` and the commit's monitoring assessment
before claiming live execution: `/readyz` only checks configuration and storage.

Full automatic assessments use the project’s normal assessment budget, clamped to
operator limits (default ceiling: 400k tokens / $10 per assessment). The legacy
monitoring budget remains for the impact-policy path when this rollout is disabled.


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
