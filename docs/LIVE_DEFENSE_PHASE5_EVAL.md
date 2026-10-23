# Live Defense Phase 5 — shadow-pilot readiness evaluation

Status: **observed on `feat/live-defense-phase5-pilot-readiness`**.
This is **not** customer-production enforcement and **not** a claim that
shadow mode prevented breaches. HTTP 200 is not attack success and is not a
healthy verdict.

Base: `origin/main` `09e8cab`. Phase 4 PR #393 is **not** included.
Codex/`rl-defense/` untouched.

## What was exercised

Owner registers an owned-test staging app → issues ingest token → authenticated
ingest → rotate credential (old token 401, new token 202) → shadow-verify from
records → export pilot report → disconnect (ingest 401). Health stays unknown.

## Observed metrics

Recorded in pytest / Playwright runs on this branch (see overnight report for
exact command output). No Gym scores. No production arm.

## Unavailable / not measured

| Claim | Why unavailable |
|---|---|
| Shadow prevented breaches | Not a supported claim; listed on the report as unsupported |
| HTTP 200 means an attack succeeded | Ingest 202 records counters; it is not exploit proof |
| Production compromise reduced | No production environment |
| Autonomous enforcement | Not implemented; PR #393 is a separate owned-test control PR |

## Screenshots

- `/cursor/stores/self/media/live-defense-phase5/` (copied from Playwright evidence when the e2e stack is run)
