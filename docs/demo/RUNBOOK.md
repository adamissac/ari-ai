# ARI demo runbook

A 3 to 5 minute walkthrough of implemented behavior. Distinguish the source of each
screen rather than presenting sample data or saved evidence as a new live run.

| Kind | What it is | How it is labelled |
|---|---|---|
| Demo account | `/access` opens the real console on a recorded, renamed Lumen Pay sample account. The browser replays captured API fixtures without calling the backend. | “Demo account · Lumen Pay sample data — every repository, commit and result here is illustrative.” |
| Recorded live evidence | One saved seven-agent run on `claude-opus-5-5` (M3, 2026-10-17, $1.39), displayed separately from the sample account's results. | “Recorded live run · not simulated” and “Replay of recorded run”. |
| Real stack, scripted model | Real API, PostgreSQL, worker, sandbox checks, Patch, Verify and artifacts; model replies are test-only scripted responses. | Persisted `provider_mode=fake`, labelled as not live in the UI. |

The recorded panel is saved evidence from an owned test fixture, not activity from
the sample customer account and not a run happening now. It predates the stricter
unpatched-test check: the new regression test was **not run on the unpatched
snapshot**, so this recording does **not establish red-to-green proof**.

The Defense Lab replays simulation evaluations and recommends responses. It does
not defend production systems or automatically apply containment actions.

## Prerequisites

Run the commands below from the **repository root**. Subshells keep later commands
in that directory. Use Python 3.12 and a supported Node version: `^22.22.2` or
`>=24.15.0` (see `frontend/package.json`).

```sh
node --version
uv --version
uv sync --frozen --python 3.12
(cd frontend && npm ci --prefix transport && npm run build --prefix transport && npm ci)
```

Tracks A and B need no live-provider key or GitHub App. Track A needs
`DEMO_ACCESS_CODE` configured in the frontend server environment; keep its value
private and out of Git. An unset code leaves the demo account closed.

## Track A: real console with recorded sample data

```sh
(cd frontend && npm run dev)
```

Open `http://localhost:3000/access`, enter the configured access code, and use the
real console pages for Analytics, Commits, Findings, Approvals, Settings, and an
assessment. `/demo` and legacy `/demo/**` links redirect to Analytics after the
gate. The account is recorded, renamed sample data; its results are illustrative.
Actions are disabled and the demo transport makes no backend calls.

## Track B: real stack with scripted model replies

```sh
(cd frontend && ../.venv/bin/python tests/e2e/stack.py)
```

The harness starts FastAPI, PostgreSQL, the worker and Next.js, then drives a real
assessment of the owned `examples/payments-lite` fixture through signed webhook,
review, seven agents, approval, Patch and Verify. Model replies are scripted and
labelled not live. The harness supplies a test-only demo access code and shuts its
services down when it exits. To use installed Chrome, set `E2E_BROWSER_CHANNEL=chrome`
for this command; otherwise install Playwright Chromium first.

## Track C: a real console against your own backend

In one terminal, from the repository root:

```sh
make dev
```

In another terminal, also from the repository root:

```sh
(cd frontend && BACKEND_ORIGIN=http://127.0.0.1:8000 NEXT_PUBLIC_DEV_LOGIN=1 npm run dev)
```

GitHub repository selection needs the configured GitHub App/OAuth integration and
an installation on the authorized test repository. Webhook signatures remain
verified. If that setup or network access is unavailable, use Track A or B.
A new live assessment can call a paid provider; do not start one without the
owner's authorization and budget. This runbook does not authorize such a call.

## Walkthrough

1. **Problem:** every push can break intended behavior or authorization.
2. **Sample account:** sign in at `/access` and point out the persistent banner. Say
   “This is recorded, renamed sample data; it is not customer activity.”
3. **Review workflow:** open Commits, a completed assessment, and its Review pipeline;
   then show Findings and a finding detail in the real console.
4. **Human control:** open Approvals and show the pending item. The account is
   read-only, and no action is sent to the backend.
5. **Limits:** the browser replays captured records, including captured non-200
   responses. No clean assessment outcome was captured.

## Evidence and release gate

- The historical report artifact is
  `security-agents/tests/artifacts/live/20261017T205333Z-seven_roles_end_to_end.json`.
  It is gitignored and retained by Alan, as recorded in `coordination/MILESTONES.md`;
  request that artifact for an independent audit.
- Current code requires stricter clean reproduction on unpatched code. That does
  not retroactively prove the historical run satisfied the newer check.
- Keep recorded, scripted and illustrative evidence distinct; do not claim broad
  precision/recall, production isolation or production RL defense from this demo.
- Before presenting a deployed commit, check its frontend `static-and-unit` and
  `e2e` CI results. A configured access code is also required for Track A.
