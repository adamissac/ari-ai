# Execution evidence

Product source tested: dd530ae3b00d31ecc54a6fb5908a50b8b6b1965d.
Audit additions: strict tests and this report only. No product fix was applied.
All commands ran in an isolated worktree with Python 3.12 and local embedded PostgreSQL 16. Providers were scripted, `RUN_LIVE_LLM_EVAL=0`, and both provider-key variables were blank. Local PostgreSQL startup/test commands required permission to use local sockets/cache directories.

For Python commands, prepend:

```sh
export PYTHONPATH=backend:shared:standards:monitoring:security-agents:code-intelligence:code-review:specialists
export RUN_LIVE_LLM_EVAL=0 ANTHROPIC_API_KEY= HACKATL_LIVE_ANTHROPIC_API_KEY=
```

Use a Python environment with the repository's locked dependencies. This run used the existing workspace venv without altering it; the Vercel SDK was supplied from an isolated `/tmp/ari-review-runtime` target for the security-agent suite. Existing Torch/Gym site packages and `rl-defense` were added only for the RL integration regressions. The full backend capture was completed before adding the new failing audit files.

| Log | Command | Exit |
|---|---|---|
| backend.log | `python -m pytest -q backend/tests` | 0 |
| focused.log | `python -m pytest -q backend/tests/live_defense_e2e/test_independent_integration.py backend/tests/live_defense_e2e/test_exec_reliability_compat.py backend/tests/test_live_defense_phase7c_review.py backend/tests/test_release_rereview_populated_migration.py backend/tests/test_parallel_migrations.py` | 0 |
| probes-all.log | `python -m pytest -q backend/tests/live_defense_e2e/test_release_rereview.py backend/tests/test_release_rereview_migrations.py` | 1, six expected reproducing failures |
| security.log | `python -m pytest -q security-agents/tests shared/tests` | 0 |
| cross-security.log | `TSC=frontend/node_modules/.bin/tsc python -m pytest -q tests/security shared/tests/test_contracts.py` | 0 |
| rl.log | `python -m pytest -q backend/tests/test_rl_integration.py backend/tests/test_rl_expectations.py backend/tests/test_rl_expectations_real_index.py backend/tests/test_runtime_ingest.py` | 0 |
| frontend.log / transport.log | `npm test` in frontend / frontend/transport | 0 |
| lint.log / typecheck.log / build.log | `npm run lint`, `npm run typecheck`, `NEXT_PUBLIC_DEV_LOGIN=1 npm run build` in frontend | 0 |
| browser.log | Local real-stack command below, all 49 tests | 0 |
| mypy.log | configured `mypy` | 0 |
| ruff.log / format.log | `ruff check backend shared monitoring standards`, `ruff format --check backend shared monitoring standards` | 0 |
| export.log / examples.log | `python -m shared.export --check`, `python -m shared.examples --check` | 0 |
| readiness.log / readiness.json | `python deploy/release_readiness.py --out /tmp/ari-rereview-readiness` | 0 |
| standalone-e2e.log | On standalone 611c38ce: `python -m pytest -q -rx backend/tests/live_defense_e2e/test_exec_reliability_compat.py` | 0; one strict xfail |
| standalone-f7-strict.log | On standalone 611c38ce: `python -m pytest -q --runxfail backend/tests/live_defense_e2e/test_exec_reliability_compat.py::test_agent_step_jobs_have_durable_deadline` | 1 |

Browser command from frontend:

```sh
RUN_LIVE_LLM_EVAL=0 ANTHROPIC_API_KEY= HACKATL_LIVE_ANTHROPIC_API_KEY= \
E2E_BROWSER_CHANNEL=chrome E2E_SKIP_BUILD=1 \
PYTHONPATH=../backend:../shared:../standards:../monitoring:../security-agents:../code-intelligence:../code-review:../specialists \
python tests/e2e/stack.py
```

A local production frontend build with `NEXT_PUBLIC_DEV_LOGIN=1` preceded this command. This is local fake-provider E2E evidence, not a deployed/customer environment.

The crash probe intentionally exits only its own child process at the provider boundary; it never kills other workers. The migration probe constructs exact upstream scripts from pinned Git objects and creates/drops only its own disposable databases. New assertions are deliberately unmarked and must fail until fixed. Captured logs replace synthetic secret-shaped fixtures with `[REDACTED_SYNTHETIC_TEST_SECRET]`; raw JUnit is not included.
