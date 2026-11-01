# YC demo runbook (90–120 s)

Read [DEMO_PREREQUISITES.md](DEMO_PREREQUISITES.md) first. Words to say are in
[DEMO_SCRIPT.md](DEMO_SCRIPT.md). This page is only the clicks.

## Pick the path before anything else

There are two paths, and the recording must say which one it is.

| | **Path A — live hosted** | **Path B — local real stack, scripted model** |
|---|---|---|
| Where | `https://ari-ai-lake.vercel.app` + Railway backend | Your laptop: real API, PostgreSQL, worker, sandbox, Next |
| Model replies | Live Claude calls | Scripted (TEST-ONLY transport), labelled **Not a live-provider run** |
| Real | Everything | Everything except the model's words: tests, sandbox checks, approvals, Patch, Verify, persistence |
| Use when | **Every** gate below is true, checked by someone other than the presenter | Any gate is false |

**Path A gates (all required; record who checked and when):**

1. `curl -s https://ari-ai-lake.vercel.app/api/frontend-version` shows `"backendReachable":true` and `"sameCommit":true`.
2. Signing in with GitHub reaches **Organizations** without an error.
3. A bookmarked assessment on the company-owned staging repository shows **Completed**, **Live provider run**, at least one confirmed finding with executed evidence, and a fix accepted by the independent re-test (DEMO_PREREQUISITES item 5).
4. Codex's release gate (#739 or its successor) does not list an open blocker for the pages shown.

**Status on 2026-10-31 (18:58Z): Path A is not available.** The Railway backend returned
`404 Application not found` (`x-railway-fallback: true`), `/api/frontend-version` reported
`backendReachable:false`, and no live hosted assessment has been recorded. Use Path B until
Devin/the Railway operator restore production and gate 3 is met.

# Path A — live hosted

## Before you press record (5 minutes)

1. Sign in at `https://ari-ai-lake.vercel.app` with GitHub.
2. Open the bookmarked **completed** assessment (prerequisite 5). Confirm it shows
   **Completed**, **Live provider run** and the **What this check did** panel.
3. Open, in separate tabs, in this order:
   - Tab 1: `https://ari-ai-lake.vercel.app` (landing page, scrolled to top)
   - Tab 2: `/connect` (Organizations)
   - Tab 3: the project's **Commits** page for the staging repo
   - Tab 4: the completed assessment page
   - Tab 5: the confirmed security finding (click it from Tab 4 once, then leave it open)
   - Tab 6: the project's **Settings** page, scrolled to **Repositories**
4. Do **not** start a new assessment while recording.

## Recording — click path

| Time | Tab | Do this | Make sure the viewer sees |
|---|---|---|---|
| 0:00 | 1 | Stay on the hero. | Headline and "Seven agents" |
| 0:12 | 2 | Switch tab. Scroll slowly once. | GitHub App permissions, **What happens when you connect a repository** |
| 0:25 | 3 | Switch tab. Click the commit row that was assessed. | Commit list, **Runs & replay** row with **Completed** |
| 0:35 | 4 | Switch tab. Pause on the top. | **Completed**, **Live provider run**, **What this check did** (Found / Fix approval / Fix proposed / Fix verified / Changed in your repository) |
| 0:50 | 4 | Scroll to the agent relay. | Agents marked **Finished**, the **Human approval** gate |
| 1:00 | 5 | Switch tab. Scroll through **What happened**, then **Before and after the fix**. | "An approved test reproduced the issue", the red/green diff, "Independent re-test accepted the fix", "not merged or deployed" |
| 1:25 | 5 | Scroll to **Evidence chain**. | Hypothesis → validation → patch → verification |
| 1:35 | 6 | Switch tab. | **Automatic reviews** switch and fix-delivery options |
| 1:50 | — | Stop recording. | — |

## If something goes wrong

| Symptom | Do this |
|---|---|
| Any page shows **Backend unreachable**, **The Ari service is not running right now**, or a red error | Stop. Reload the tab. If it persists, switch to Path B. Do not record the hosted path with an error on screen. |
| The assessment page shows **Not a live-provider run** | It is not a live run. Either use a different bookmarked run or say "scripted model replies" on screen. |
| Sign-in loops back to the sign-in page | Sign out, clear cookies for the site, sign in again before recording. |

# Path B — local real stack, scripted model replies

One terminal, from the repository root:

```sh
cd frontend && ../.venv/bin/python tests/e2e/stack_manual.py
```

Wait for `[manual stack] READY` and open the `web:` URL it prints. Sign in with the
development login `e2e-alice`. Then:

1. **Projects → acme → payments-lite** and click **Continue** through Setup; on question 6 click
   **Approve sandbox testing for 30 days**; on question 8 click **Finish setup**
   (the "Start first assessment" button fails on this stack because there is no real GitHub).
2. Open **Commits**, click the top commit, scroll to **Start an assessment**, paste the
   `commit:` SHA printed by the script, click **Start assessment**.
3. On the assessment page click **Approve remediation → Confirm approval** for each fix request.
   The run completes in about 30 seconds.
4. Now follow the Path A click path using this stack's pages (skip Tab 1's hosted URL; use the
   stack's own `/`). The yellow **Not a live-provider run** banner stays visible: say "model
   replies are scripted for this recording" when the assessment page first appears, and keep
   the banner in frame.
5. The repository here is `examples/payments-lite`, a company-owned demo service seeded with
   known bugs. Say so. It is not a customer repository.

Stop the stack with Ctrl-C when done; it deletes its temporary database.
