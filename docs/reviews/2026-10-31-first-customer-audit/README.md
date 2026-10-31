# First-customer journey audit (2026-10-31)

Base: `main` @ `9437e217`. Method: walked the real local stack
(`frontend/tests/e2e/stack_manual.py`: FastAPI, PostgreSQL, worker, Next production build,
scripted model replies labelled not live) at 1440×900 as `e2e-alice`: sign-in → Organizations →
repository → 8-question Setup → first assessment → approval → completed run → finding →
Settings; then a cancelled run. Builds on, and does not edit, the files of open PR #696
(setup, findings list, approvals, project overview, stepper, `lib/api.ts`, `ui/index.tsx`).

## P0 — blocks a real user

| # | Issue | Status |
|---|---|---|
| P0-1 | **Live hosted assessment unverified.** `docs/deploy/RAILWAY_AND_GITHUB_APP.md` records live production run verification as outstanding. Nothing in the frontend can prove the hosted journey works end to end. | Backend/ops handoff (Devin); demo uses the fallback until done |
| P0-2 | Setup "Start first assessment" failure (`SUBSYSTEM_UNAVAILABLE: could not read the latest commit from GitHub`) appears at the top of the page, away from the button, and **Finish setup** then says "You're set up" with no sign that no check ran. | Fixed in **PR #696** (inline recovery); "You're set up" copy left to #696 to avoid overlap |

## P1 — reduces trust or clarity

| # | Issue | Status |
|---|---|---|
| P1-1 | A failed / cancelled / budget-exhausted assessment showed only `Assessment error · CODE` and the raw message; no cause in plain words and no way to re-run. | **Fixed here**: "This check did not finish" panel with cause, what finished, "not a clean result", and **Start a new check of commit …** (prefilled, still requires the approved scope) |
| P1-2 | A completed run with no findings said only "No findings were recorded by this run." | **Fixed here**: states what ran, and "limited coverage" when security agents did not test, an agent failed, or model turns were not live; otherwise "not proof that the application is secure" |
| P1-3 | Completed runs did not separate found / approved / proposed / verified / delivered. | **Fixed here**: "What this check did" panel from persisted findings, agent runs and approvals |
| P1-4 | Phase list showed **Skipped** for phases the run had already finished (stale log for up to 5 s), contradicting the agent relay right above it. Heading said "six phases"; five are shown. | **Fixed here**: phase log reloads with each stream event; heading "Progress through each phase" |
| P1-5 | Long-running check gave no sense of time or that it continues server-side. | **Fixed here**: elapsed time and "keeps running if you leave this page" |
| P1-6 | Organizations page did not say what connecting does (it can open an `ari/build-recipe` PR); empty state with no install URL was a dead end. | **Fixed here** |
| P1-7 | Connect error rendered under a possibly long repository list, out of view. | **Fixed here**: shown above the list |
| P1-8 | Start-assessment scope dropdown showed `Authorize rep_01…`; commit had to be retyped although one was selected. | **Fixed here**: "Sandbox testing for owner/repo"; `?commit=` prefills |
| P1-9 | Terminology drift: assessment / check / review / run; fix delivery "Ask me first" (Setup) vs "Manual" (Settings) vs "Ask before each fix" (#696 Approvals). | Open. Needs one glossary pass after #696 merges (touches #696 files) |
| P1-10 | Setup summary lists "Review pushes: Yes" next to "Review new commits automatically: No" — reads as a contradiction. | Open (Setup is #696 territory) |

## P2 (not addressed)

Duplicate "Analyze this commit →" links on Commits; seven-step stepper on `/connect` vs eight Setup questions (fixed by #696).

## Backend handoff (Devin)

No backend change is in this PR. Needed for launch, in priority order:

1. **Verify one live assessment on the hosted stack** against a company-owned staging repository
   (GitHub App fetch → worker → sandbox → Patch/Verify) and record its assessment URL. This is
   the demo's primary path (`docs/demo/yc-w27/DEMO_PREREQUISITES.md` item 5).
2. Persist a machine-readable coverage record per assessment (which checks/entry points were
   tested). The frontend currently derives coverage from agent runs only, which is honest but coarse.
3. Open PR #725 (restart after lost worker state; FAILED always carries an error) supports P1-1;
   merging it makes the "did not finish" panel always show a cause.
4. During the e2e run the worker logged `register_verified_regression` jobs ending **dead** with
   `RuntimeError: SNAPSHOT_NOT_READY: Regression waits for a canonical assessment snapshot`
   (`backend/backend/intelligence_jobs.py:36`). Tests still pass; confirm whether verified fixes
   are silently missing their regression registration.

## Evidence

- `npm run lint`, `npm run typecheck`: clean. `npx vitest run`: 110 files, 481 tests passed.
- `stack.py` (real API + PostgreSQL + worker + Next + Playwright, Chrome): `journey`, `honesty`,
  `conflict-recovery`, `onboarding`, `pages`, `demo-recovery` specs — 28 passed.
- Manual browser walkthrough on `stack_manual.py`: setup → start (commit prefilled, scope
  "Sandbox testing for acme/payments-lite") → phases update live → approve two fixes → outcome
  "2 confirmed / 2 approved / 2 proposed / 2 verified"; second run cancelled → "This check did not
  finish" with a working restart link.

