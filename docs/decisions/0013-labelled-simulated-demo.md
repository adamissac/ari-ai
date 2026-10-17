# ADR-0013: A labelled, self-contained simulated demo at /demo

| Field | Value |
|---|---|
| Status | Proposed |
| Date | 2026-10-17 |
| Deciders | Adam (product owner request recorded in session); team ratification pending |
| Related | docs/14 "Demo considerations", docs/20, `frontend/app/demo/`, `frontend/lib/demo/` |

## Context
The product owner asked for a demo that starts with a GitHub-style sign-in, lists an
organization's repositories and recent commits, and lets a viewer open any commit to see
the code review, all seven security agents and the Defense Lab — without a backend,
GitHub App, sandbox or model key.

docs/14 and docs/20 forbid fabricated runs in the console: a demo there may only slow
down the replay of a recorded real run. That rule protects the console's promise that
every number comes from saved records.

## Decision
1. The demo lives at its own route, `/demo`, outside the console and the session gate.
   It never calls the backend or GitHub, and it never mixes its values with records.
2. Every demo page shows a "Simulated demo" marker. The footer on `/demo` says the
   accounts, repositories, commits and agent runs are illustrative.
3. The illustrative content is hand-written in `frontend/lib/demo/` and shaped like the
   real contracts: agent runs with tool calls (including policy denials), findings with
   CWE and CVSS, generated tests that fail before and pass after a fix, and a
   continuous-defense map. The stories follow the project's planted-defect target
   (`examples/payments-lite`). Organizations and people are invented.
4. The Defense Lab itself (`/lab`) stays records-only: its new command-center map
   replays a recorded game from the validated evaluation bundle.
5. The console rule in docs/14 and docs/20 is unchanged for every route except `/demo`.

## Consequences
- Viewers can follow the whole product loop in about a minute on any machine.
- The demo can drift from real agent behaviour. When contracts or agent roles change,
  update `frontend/lib/demo/scenarios.ts`; the unit tests check agent order, verdict
  consistency and component references.
- Anyone presenting it must call it a simulated walkthrough. It is never evidence that
  the agents found or fixed anything.
