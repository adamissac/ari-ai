# MSG: Live Defense Phase 1 UI — contracts the frontend needs (no shared/ change)

- ID: `20261022T091500Z-alan-to-all-live-defense-pilot-ui`
- From: alan
- To: all (vihaan, adam, sai, sarosh; backend/shared interim)
- Kind: `integration`
- Timestamp (UTC): 2026-10-22T09:15:00Z
- Branch / commit / PR or issue link: `feat/live-defense-pilot-ui` (draft PR)
- Related subsystem(s): frontend, backend, shared, monitoring, rl-defense (read-only)
- Summary (facts, not assumptions):
  - New customer Live Defense dashboard: `/projects/{id}/live-defense` (Overview, Investigation, Explainability) plus isolated sample layout at `/live-defense-pilot` and `?preview=layout`.
  - Live mode uses only existing APIs: project 24/7 switch, events, reassessments, incidents, defense-recommendations, explanations, rl-evaluations.
  - Sample layout is labelled and never mixed with records. No apply / isolate / rate-limit / block actions.
  - `rl-defense/` and `shared/` were not changed. Missing live-graph / connected-app / live-incident / live-inference endpoints are documented in `docs/planning/LIVE_DEFENSE_FRONTEND_API.md` for the next backend owner (Devin).
- Breaking change? migration/test impact: None to `shared/` or generated TS. Frontend unit tests cover mode isolation, empty live map, and no enforcement controls.
- Action required by recipient: Backend/shared owner — do not treat layout-preview fixtures as a contract. If you add types, follow CONTRACTS.md (proposal → shared → generate → consumers). Vihaan — Live Defense sits under More; Monitoring links to it. Adam — Lab remains the recorded evaluation; this UI does not read checkpoints.
- Evidence: see the draft PR (lint, typecheck, vitest, `next build` reported there).
