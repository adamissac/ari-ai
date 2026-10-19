# Ownership and nonconflicting implementation lanes

| Owner | Writes | Consumers and dependencies |
|---|---|---|
| Adam | `rl-defense/`; RL-specific tests, fixture scenarios | Srihith: recommendation DTO; Vihaan: model metrics UI |
| Alan | `security-agents/`; security-specific tests, sandbox execution driver | Sarosh context packs; Srihith gateway/approvals; Sai sandbox API |
| Sarosh | `code-intelligence/`; structural index and retrieval tests | Srihith snapshot persistence; Sai/Alan consumers |
| Sai | `code-review/`; reviewer, intent, test/repair loops | Sarosh intelligence; Alan sandbox/Verify; Srihith jobs |
| Vihaan | `frontend/`; browser UI/e2e tests | Srihith OpenAPI types/SSE; others evidence UX |
| ~~Srihith~~ (left the project, 2026-10-19) | `backend/`, `monitoring/`, `shared/`; migrations, queue, auth, API, webhook, Compose | everyone |

**Interim (2026-10-19, until the team reassigns):** Srihith is no longer on the project.
Alan is interim approver for `shared/` contract changes. Affected consumer owners still
review per CONTRACTS.md. `backend/` and `monitoring/` have no named owner yet; changes
there need a PR reviewed by any remaining owner. See
`coordination/messages/20261019T070000Z-alan-to-all-srihith-handover.md`.

`examples/`, `tests/`, `.github/`, `scripts/`, `docs/` are shared: announce material changes and minimize conflicts. Never merge another owner's implementation without reviewing their PR and checks. Everyone can read everything; ownership governs writes, not comprehension.
