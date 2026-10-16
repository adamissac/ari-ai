# CI workflows — planned, not configured

**No workflows exist yet, on purpose.** There is no application code to build or
test, and a pipeline that "passes" on an empty repo would be misleading. Each
workflow below is added by the task that first creates something for it to check.

| Workflow file (planned) | Triggers | Jobs | Added by |
|---|---|---|---|
| `docs.yml` | PR touching `**/*.md` | Markdown link check, Mermaid syntax check | `INFRA-003` |
| `secrets.yml` | every PR + push to `main` | gitleaks scan of the diff | `INFRA-003` |
| `backend.yml` | PR touching `backend/`, `shared/`, `security-agents/`, `code-*`, `monitoring/` | ruff, mypy, pytest (unit), contract tests | `CORE-002` |
| `frontend.yml` | PR touching `frontend/`, `shared/generated/` | eslint, tsc, unit tests, build | `UI-001` |
| `contracts.yml` | PR touching `shared/` | regenerate JSON Schema + TS, fail if diff is dirty | `CORE-003` |
| `rl.yml` | PR touching `rl-defense/` | env API checks (`gymnasium.utils.env_checker`), determinism test, short smoke train (CPU, < 5 min) | `RL-001` |
| `e2e.yml` | nightly + manual | docker compose up; demo-scenario e2e against `examples/` target | `TEST-005` |

## Rules for future workflows

- Least-privilege `permissions:` block on every workflow (`contents: read` default).
- Pin third-party actions to a full commit SHA.
- No secrets exposed to workflows triggered by forks (`pull_request_target` is banned
  unless reviewed by the security owner).
- Live-LLM evaluation suites never run on PRs automatically (cost + secret exposure);
  they run manually or on schedule with a budget cap.
- Use only free GitHub Actions minutes unless paid usage is approved.
