# Deployment topology

Status: **specified; nothing provisioned.** Spec: [18](../18_INFRASTRUCTURE_AND_DEPLOYMENT.md).

## Local / demo (MVP)

```mermaid
flowchart TB
  subgraph Laptop[Developer or demo laptop]
    FE[frontend :3000] --> API[api :8000]
    API --> PG[(postgres :5432)]
    W[worker] --> PG
    W --> DS[Docker daemon]
    DS --> S1[[sandbox: test-runner]]
    DS --> S2[[sandbox: check-runner]]
    DS --> T[[target: payments-lite]]
    S2 -. internal network only .- T
  end
  W --> AN[Anthropic API]
  W --> GH[GitHub]
  GH -. webhook via tunnel or replay .-> API
```

## Hosted option (only if approved, post-MVP)

| Piece | Host | Note |
|---|---|---|
| Frontend | Vercel (free tier) | Static + SSR |
| API | Railway (free/trial) | No Docker socket needed |
| Worker + sandboxes | Dedicated VM with Docker/gVisor | Paid; requires approval and ADR |
| Postgres | Managed free tier | Backups needed |

The API can be hosted without the worker; a hosted deployment without a sandbox
host can show results but not run assessments.
