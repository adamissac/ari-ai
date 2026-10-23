# Live Defense Phase 5 — shadow-pilot readiness evaluation

Status: **observed on `feat/live-defense-phase5-pilot-readiness`**.
This is **not** customer-production enforcement and **not** a claim that
shadow mode prevented breaches. HTTP 200 is not attack success and is not a
healthy verdict.

Base after merge: `origin/main` `cb40ca6` (includes PR #394 Codex RL-CMDP-002
research). Original Phase 5 commit was from `09e8cab`. Phase 4 PR #393 is
**not** included. Codex research files arrived only via merge of main; they
were not edited on this branch. No training or promotion.

## What was exercised

Owner registers an owned-test staging app → issues ingest token → authenticated
ingest → rotate credential (old token 401, new token 202) → shadow-verify from
records → export pilot report → disconnect (ingest 401). Health stays unknown.
Analyst accept still does not execute a control. No apply / isolate / rate-limit
/ block buttons.

## Observed commands (executed on this branch after merging `origin/main`)

```
make check
  ruff pass; format 166 files; shared.export --check 127 files; examples check pass

uv run mypy
  Success: no issues found in 40 source files

uv run pytest -q backend/tests monitoring/tests shared/tests --ignore=backend/tests/test_unified_assessment.py
  274 passed, 8 skipped in 90.61s
  skips: rl_defense missing (4), Docker sandbox (2), live LLM opt-in (1), TSC unset (1)

npm run lint --prefix frontend && npm run typecheck --prefix frontend
  pass

npm test --prefix frontend
  325 passed / 77 files in 17.47s

npm test --prefix frontend/transport
  35 passed

cd frontend && NEXT_PUBLIC_DEV_LOGIN=1 E2E_BROWSER_CHANNEL=chrome ../.venv/bin/python tests/e2e/stack.py tests/e2e/live-defense.spec.ts
  2 passed (9.6s) after waiting for the rotated token text
  (earlier skip-build without DEV_LOGIN timed out on GitHub login; a later run
  failed Playwright strict mode on two “disconnected” nodes, then raced the
  rotate token text — both test-only, then green)

gitleaks git --log-opts='origin/main..HEAD'
  2 commits scanned, no leaks (pre-final commit; re-run after push)
```

Alembic head remains `0011` (`backend/backend/migrations/versions/0011_live_policy_decisions.py`).
Disconnect lives in application `doc` JSON. No `/controls` routes in the Next
build. OpenAPI POST paths contain rotate/disconnect/shadow-verify and do not
contain isolate / block-source / rate-limit / apply.

## Unavailable / not measured

| Claim | Why unavailable |
|---|---|
| Shadow prevented breaches | Not a supported claim; listed on the report as unsupported |
| HTTP 200 means an attack succeeded | Ingest 202 records counters; it is not exploit proof |
| Production compromise reduced | No production environment |
| Autonomous enforcement | Not implemented; PR #393 is a separate owned-test control PR |
| Worker/telemetry/policy healthy | No health-check producer; fields stay `unknown` |

## Screenshots

Copied from Playwright evidence:

- `/cursor/stores/self/media/live-defense-phase5/live-defense-apps.png`
- `/cursor/stores/self/media/live-defense-phase5/live-defense-overview.png`
- `/cursor/stores/self/media/live-defense-phase5/live-defense-investigation.png`
- `/cursor/stores/self/media/live-defense-phase5/live-defense-incident.png`
- `/cursor/stores/self/media/live-defense-phase5/live-defense-explain-review.png`
- `/cursor/stores/self/media/live-defense-phase5/live-defense-phase5-report.png`
- `/cursor/stores/self/media/live-defense-phase5/live-defense-phase5-disconnect.png`
