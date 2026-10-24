# Live Defense end-to-end suite (Workstream 2)

Owner: Alan Mozhoor. Branch: `feat/devin-live-defense-e2e`.

Automated owned-staging integration tests for the first-responder pipeline,
in `backend/tests/live_defense_e2e/` (runbook: that directory's `README.md`).
Scenarios A–H run on real HTTP routes, real PostgreSQL, the real durable job
queue and the real `security_agents` runtime; the model is scripted
(`provider_mode="fake"` everywhere). FakeLLM results do not validate real
Anthropic execution — the only live test is opt-in (`live_llm`).

## Commands

| Tier | Command | Runs in CI |
|---|---|---|
| Fast smoke | `make e2e-ld-smoke` | yes (PR) |
| Full integration (A–H) | `make e2e-ld` | yes (PR) |
| Failure injection (D–F) | `make e2e-ld-fault` | yes (PR) |
| Live provider (opt-in, costs money) | `make e2e-ld-live` | manual only |

CI: `.github/workflows/live-defense-e2e.yml`. Machine-readable results land in
`test-results/live-defense-e2e/` (git-ignored; uploaded as CI artifacts).

## Coordination notes

- Depends on the unmerged Phase 7C agent-execution stack (PR #458); this branch
  is based on its tip. None of that PR's files are modified here.
- Bugs this suite surfaces in other workstreams get focused issues, not
  in-place fixes.
- `docs/planning/SESSION_HANDOFF.md`, `docs/planning/HACKATL_TASKS.md` and
  `CHANGELOG.md` are intentionally untouched: PR #458 edits them, and the
  workstream instruction is to avoid those files.
