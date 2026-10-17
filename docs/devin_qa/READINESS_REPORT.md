# QA execution evidence

This records executed checks, not a blanket readiness or deployment claim.

The original QA proposal in PR #94 had not been executed. Continuation `fix/srihith/qa-reliability` replaces invalid package imports (`backend.backend`, `shared.shared`), the nonexistent `test:unit` npm command, unbounded install behavior during checks, and skip-as-success summaries with entry points to the existing suites.

Executed on macOS arm64 / Python 3.12, using the installed workspace environment:

- Runner semantics: `python -m unittest discover -s tests/qa -v` — 10 passed, including timeout, missing executable, unknown status, invalid readiness JSON, disabled live calls, and exit-code propagation.
- Frontend entry point with `--browser` and `E2E_BROWSER_CHANNEL=chrome` — transport build, TypeScript, ESLint, Vitest32 and real API/PostgreSQL/worker/Chrome12 tests passed.
- Security entry point — generated contracts110-file freshness and catalog integrity passed; backend/monitoring/reviewer/intelligence162 passed with7 optional skips. The separate security-agent suite394 passed with11 optional skips.
- Preflight invoked from `/tmp` using an absolute script path — exit2, correctly reporting absent Docker, optional RL package and running local API as incomplete. No raw credentials are read or printed.
- RL entry point — exit2, optional RL environment absent. No RL test execution is claimed for this local run.

For current product gates, consult [MILESTONES](../../coordination/MILESTONES.md), the [session handoff](../planning/SESSION_HANDOFF.md) and the PR’s CI checks. Compose is already exercised in container CI; the functional repair flow and console pages are merged; the signed-push-to-verified-regression chain is covered by PR #93. These are not outstanding blockers merely because this laptop has no running stack.

Remaining independent evidence boundaries: real provider runs require explicit authorization and credentials; real GitHub installation/webhook delivery needs its setup; hardened sandbox and deployed uptime claims require their own executed evidence. A static check, successful import, or screenshot cannot establish them.
