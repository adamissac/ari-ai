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
policy. The allowlist checks GitHub's commit author account, not the push sender.
An installed App, connected repository, enabled monitoring and approved repository
scope remain prerequisites. Approving a scope wakes blocked automatic commits.
Opening the commit page is unnecessary; it polls the persisted run when visited.
Check worker logs for `assess_github_commit` and the commit's monitoring assessment
before claiming live execution: `/readyz` only checks configuration and storage.
