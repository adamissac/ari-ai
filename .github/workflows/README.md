# CI workflows — planned, not configured

Each workflow below is added by the task that first creates something for it to
check. **Implemented:** `docs.yml`, `secrets.yml` (INFRA-003), `backend.yml` (CORE-002/003), `rl.yml` (RL-001), `examples.yml` (DEMO-001), `security-agents.yml` (SEC). The others are still planned.

| Workflow file (planned) | Triggers | Jobs | Added by |
|---|---|---|---|
| `docs.yml` ✅ | PR touching `**/*.md` | Markdown link + anchor check, Mermaid block-type check | `INFRA-003` |
| `secrets.yml` ✅ | every PR + push to `main` | gitleaks scan of full history with `.gitleaks.toml` (adds a rule for every `sk-ant-*` key form) | `INFRA-003` |
| `backend.yml` ✅ | PR touching `backend/`, `shared/`, `monitoring/` | ruff, mypy, generated-contract freshness, pytest against a Postgres service (incl. TS compile of generated types) | `CORE-002` |
| `frontend.yml` | PR touching `frontend/`, `shared/generated/` | eslint, tsc, unit tests, build | `UI-001` |
| `contracts.yml` | PR touching `shared/` | folded into `backend.yml` (`shared.export --check`, `shared.examples --check`) | `CORE-003` |
| `rl.yml` ✅ | PR touching `rl-defense/` | env API checks (`gymnasium.utils.env_checker`), determinism test, short smoke train (CPU, < 5 min) | `RL-001` |
| `examples.yml` ✅ | PR touching `examples/` | payments-lite lint, its own tests, label checks, Docker build (non-root) | `DEMO-001` |
| `security-agents.yml` ✅ | PR touching `security-agents/`, `shared/`, `code-intelligence/`, payments-lite | ruff + the seven-agent suite (FakeLLM, real registry/scope_guard/sandbox) | `SEC` |
| `e2e.yml` | nightly + manual | docker compose up; demo-scenario e2e against `examples/` target | `TEST-005` |

## Rules for future workflows

- Least-privilege `permissions:` block on every workflow (`contents: read` default).
- Pin third-party actions to a full commit SHA.
- No secrets exposed to workflows triggered by forks (`pull_request_target` is banned
  unless reviewed by the security owner).
- Live-LLM evaluation suites never run on PRs automatically (cost + secret exposure);
  they run manually or on schedule with a budget cap.
- Use only free GitHub Actions minutes unless paid usage is approved.

## Code intelligence (INTEL-001..008)

`code-intelligence.yml` adds locked-workspace Ruff/format/strict mypy, intelligence tests
and real PostgreSQL payload/webhook integration. FakeTransport runs in CI; provider
inference is opt-in and skipped without a key.
