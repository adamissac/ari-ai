# QA entry points

These scripts run the repository’s existing checks in the currently selected Python environment. Set up that environment using the root README first. They do not install packages, load `.env`, call a live model, merge code, or deploy. Test subprocesses force `RUN_LIVE_LLM_EVAL=0`.

From the repository root:

```bash
.venv/bin/python scripts/devin_qa/preflight_check.py --json
.venv/bin/python scripts/devin_qa/verify_m7_demo.py
.venv/bin/python scripts/devin_qa/test_security_workflow.py
.venv/bin/python scripts/devin_qa/test_rl_workflow.py
.venv/bin/python scripts/devin_qa/test_frontend_integration.py --browser
.venv/bin/python scripts/devin_qa/run_all_qa_tests.py --browser
```

The scripts resolve their working directories relative to their own files. Invoking an absolute script path works from another directory. The master runner preserves the selected Python interpreter.

| Exit | Meaning |
|---|---|
| 0 | Every selected check passed |
| 1 | At least one selected check failed, including command errors and timeouts |
| 2 | Checks are incomplete because prerequisites or selected integration checks were unavailable |

Failure takes precedence over incompleteness. Skips never become passes. Underlying pytest suites print their own optional skips; a passing suite does not prove those skipped cases ran.

The preflight is read-only: it checks Python/package/executable availability, repository files, and a GET to `/readyz` at `--api-url` (default `http://127.0.0.1:8000`). A discovered package or executable does not prove imports, Docker daemon health, sandbox isolation, provider credentials, or external GitHub deliveries. Missing local services report incomplete. A malformed readiness response or a service reporting false is a failure. This check never declares the whole demo ready.

The security entry point executes backend, monitoring, reviewer and intelligence tests, checks generated contracts/catalog integrity, and runs the security-agent suite in a separate process to avoid test-package name collisions. The suites use owned lab fixtures, scripted providers and the configured test database.

The RL entry point runs `rl-defense/tests` only when the optional RL environment is installed. Simulation evidence does not demonstrate live defense. Missing RL dependencies return 2.

The frontend entry point requires installed dependencies in both `frontend` and `frontend/transport`; it builds transport, checks TypeScript and ESLint, and runs Vitest. `--browser` also builds Next and starts the actual API/PostgreSQL/worker/browser test stack. Without `--browser`, browser integration is explicitly incomplete. Set `E2E_BROWSER_CHANNEL=chrome` to use an installed Chrome with a temporary test profile. Builds write their usual generated outputs; test suites create temporary repositories/databases. Only the preflight claims read-only behavior.

Runner error/skip/readiness semantics are exercised by `python -m unittest discover -s tests/qa -v` and `.github/workflows/qa-tools.yml`. Product integration remains covered by the existing backend, security-agents, frontend and container workflows.

The M7 entry point executes the backend push-to-regression test with the selected
Python interpreter and forced live-call opt-out. The backend fixture owns a fresh
session database; the runner never starts or stops the shared development server.
It records bounded test output in ignored `.dev/qa/m7-evidence.json` (override with
`--output PATH`), preserving checked-in rehearsal evidence. Backend success still
returns 2 because this entry point does not execute browser tests. Test command or
collection failures return 1. Use the frontend browser runner for browser evidence.
