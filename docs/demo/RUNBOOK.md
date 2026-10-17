# Ari demo runbook

A 3 to 5 minute demo built only on what exists. Every screen is one of three kinds. Say which kind out loud each time:

| Kind | What it is | How it is labelled |
|---|---|---|
| **Simulated** | `/demo`: illustrative accounts, repositories, commits and agent runs. No repository is read and no model is called. | "Simulated demo" marker on every page (ADR 0013) |
| **Recorded live run** | The one live seven-agent run on `claude-opus-5-5` (M3, 2026-10-17, $1.39), shown as a replay of its saved report | "Recorded live run · not simulated" and "Replay of recorded run asm_01M55T1G74F5RQERH65HWCQB1H" |
| **Real stack, scripted model** | Real API, PostgreSQL, worker, sandbox checks, Patch, Verify and artifacts; only the model replies are scripted | Agent runs persisted with `provider_mode=fake`, shown as not live in the UI |

Never call a simulated or scripted screen "live". The RL Defense Lab is a **simulation that recommends** responses; it does not defend production systems and nothing applies its recommendations automatically.

## Prerequisites (check before going on stage)

```
node --version            # 20 or newer
uv --version              # Python 3.12 workspace
cd frontend && npm ci && npm ci --prefix transport && npm run build --prefix transport
```

No API key, GitHub App or cloud service is needed for tracks A and B.

## Track A: simulated walkthrough and recorded live run (default, offline)

```
cd frontend && npm run dev
```

Open `http://localhost:3000/demo`. The sign-in is simulated; no OAuth happens. Scroll below the sign-in card or the organization list to the **Recorded live run** panel.

## Track B: real stack with scripted model replies (optional, about 3 minutes, no key)

```
cd frontend && ../.venv/bin/python tests/e2e/stack.py --headed
```

This starts a real FastAPI, PostgreSQL, worker and Next.js stack, then drives the browser through a real assessment of `examples/payments-lite`: signed webhook, review, seven agents, approval, Patch and Verify. Model replies come from the test-only scripted transport, so every agent run is labelled as not live. The stack shuts down when the run ends.

## Track C: real console against your own backend (not for the stage)

```
make dev
cd frontend && BACKEND_ORIGIN=http://127.0.0.1:8000 NEXT_PUBLIC_DEV_LOGIN=1 npm run dev
```

- **GitHub repository selection** needs a GitHub App: `GITHUB_APP_ID`, `GITHUB_APP_PRIVATE_KEY` (or `_PATH`), `GITHUB_WEBHOOK_SECRET`, `GITHUB_OAUTH_CLIENT_ID`, `GITHUB_OAUTH_CLIENT_SECRET`, `GITHUB_APP_SLUG`, and the App installed on a test repository. Webhook signatures are always verified; there is no bypass.
- **Fallback when no repository is installed or the network is down:** use Track A, and Track B for the real backend.
- **Running a new assessment here calls a paid model.** Do not start one during the demo without the owner's approval.

## 3 to 5 minute walkthrough

1. **(0:00) The problem.** Every push can break intent or open a hole; Ari reviews, attacks safely in a sandbox, and proves fixes.
2. **(0:40) Simulated product tour** (Track A, `/demo`). Sign in, pick an org and repo, open a commit, and show review, the seven agents, the patch and Verify. Say: "This walkthrough is simulated."
3. **(2:00) Real evidence** (Recorded live run panel). Seven agents ran live on `claude-opus-5-5`. Probe confirmed the payment-detail IDOR, Patch fixed it with a new regression test, independent Verify accepted it, and Fortify hardened it, for $1.39. Say: "This is a replay of a recorded run, not running now."
4. **(3:00) Real backend** (Track B, if time allows, or a recording of it). Show the real database records and the Patch diff, with the scripted-model label visible.
5. **(4:00) Defense Lab.** A simulated network; a trained policy recommends responses. Say: "Simulation and recommendations only."
6. **(4:30) Limits.** One live run on one owned fixture, local sandbox, CLI auto-approval in that run.

## Known limitations

- Only one live seven-agent run exists (M3). The recorded panel is a hand copy of its saved report (`security-agents/tests/artifacts/live/20261017T205333Z-seven_roles_end_to_end.json`, kept locally because artifacts are gitignored).
- Track B uses scripted model replies.
- The GitHub App flow is untested on stage without a configured App and installation.
- RL results come from a simulator and are recommendations only.

## GO / NO-GO checks

- GO when Track A loads offline, the "Simulated demo" marker and the "Recorded live run" panel are both visible, and the frontend CI `static-and-unit` and `e2e` jobs are green on the commit you deploy.
- NO-GO for any claim of live execution beyond the recorded run, or of production defense.
