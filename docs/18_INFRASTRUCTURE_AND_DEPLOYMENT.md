# 18 — Infrastructure and deployment

Status: **specified; nothing is provisioned.** Constraint: **no paid
infrastructure** without explicit human approval (NFR-09). Topology diagram:
[architecture/deployment-topology](architecture/deployment-topology.md).

## Environments

| Env | Purpose | Where | Status |
|---|---|---|---|
| `development` | Each developer's laptop | Docker Compose: postgres, api, worker, frontend; sandboxes via local Docker | Planned (`INFRA-004`) |
| `demo` | HackATL presentation | Same Compose stack on a team laptop (primary) | Planned |
| `staging` | Shared preview | Vercel (frontend, free tier) + Railway (api/worker, free/trial tier) — **only if approved** | Not provisioned |
| `production` | Real users | TBD after hackathon | Not planned |

**Why the demo runs locally:** the worker needs a Docker daemon to start
sandboxes. Typical PaaS free tiers do not provide Docker-in-Docker safely. A
hosted sandbox runner is a post-MVP decision (RQ-007).

## Local stack (planned `docker-compose.yml`)

| Service | Image / build | Ports | Notes |
|---|---|---|---|
| `postgres` | `postgres:16` (pinned digest) | 5432 | Volume `pgdata` |
| `api` | `backend/Dockerfile` | 8000 | Runs migrations on start (dev only) |
| `worker` | same image, `worker` command | — | Needs Docker socket **on the host** to create sandboxes; this is the one privileged component and never runs untrusted code itself |
| `frontend` | `frontend/` dev server | 3000 | |

The worker's Docker socket access is a known risk (whoever controls the worker
controls the host Docker). Mitigation path: dedicated sandbox host or rootless
Docker / gVisor ([26](26_RISKS_AND_TRADEOFFS.md) R-03).

## Configuration

All config via environment variables, documented in [`.env.example`](../.env.example):

| Group | Variables |
|---|---|
| Environment | `APP_ENV`, `LOG_LEVEL` |
| LLM | `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` (default `claude-opus-5-5`), `ANTHROPIC_MODEL_FAST`, `AGENT_MODEL_OVERRIDES`, `LLM_MAX_TOKENS_PER_ASSESSMENT`, `LLM_MAX_USD_PER_ASSESSMENT` |
| Backend | `API_BASE_URL`, `DATABASE_URL`, `ARTIFACT_STORE_URI`, `SESSION_SECRET` |
| GitHub | `GITHUB_APP_ID`, `GITHUB_APP_PRIVATE_KEY_PATH`, `GITHUB_WEBHOOK_SECRET`, `GITHUB_OAUTH_CLIENT_ID`, `GITHUB_OAUTH_CLIENT_SECRET` |
| Sandbox | `SANDBOX_RUNTIME`, `SANDBOX_DEFAULT_TIMEOUT_SECONDS`, `SANDBOX_MAX_MEMORY_MB`, `SANDBOX_NETWORK_MODE` |
| Frontend | `NEXT_PUBLIC_API_BASE_URL` |
| RL | `RL_DEVICE`, `RL_RUNS_DIR` |

Settings are parsed once at startup by a Pydantic `Settings` class in
`backend/`; missing required values fail fast with a clear message.

## Webhooks in development

GitHub cannot reach `localhost`. Options (choose in `INFRA-004`): a free tunnel
(e.g. `smee.io` relay for webhooks) or replaying recorded webhook payloads with
`scripts/` tooling. The demo uses replay or a tunnel; never a public deployment
of the worker.

## CI/CD

GitHub Actions on free minutes, workflows added per
[.github/workflows/README](../.github/workflows/README.md). No CD in MVP.

## Secrets management

Local: `.env` (git-ignored). Hosted (if approved): platform secret stores
(Vercel/Railway env vars). GitHub App private key stored as a file path outside
the repo (`secrets/` is git-ignored).

## Cost guardrails

- LLM spend capped per assessment (`LLM_MAX_USD_PER_ASSESSMENT`) and globally by
  an org-level daily cap (default USD 25, config) enforced in the LLM gateway.
- Anthropic console spend limit set by the account owner (manual, recommended).
- RL training runs on CPU by default.
