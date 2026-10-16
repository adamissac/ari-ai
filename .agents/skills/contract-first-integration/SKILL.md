---
name: contract-first-integration
description: Create, review and evolve shared typed contracts across backend, intelligence, agents, RL and frontend. Use whenever modifying shared models or an integration boundary.
---

# contract-first-integration


1. Read `docs/12_DATA_MODELS_AND_CONTRACTS.md`, real `shared/` implementation, and `coordination/CONTRACTS.md`.
2. Determine canonical producer, consumer, current model version, evidence/commit pin, failure enums and authorization boundaries. Define specific Pydantic fields and sample valid/invalid payloads.
3. Send proposal via `coordination/messages/<unique>.md` plus GitHub issue/PR comment to all affected owners. Work behind an adapter/fixture until interface agreed.
4. Schema owner updates `shared/` as single truth; generate JSON Schema and frontend TS, run roundtrip and consumer-driven contract tests. Breaking changes require version bump and migration/compatibility notes.
5. Ensure frontend doesn't hand-maintain incompatible types and backend doesn't return mock success with missing provider. Persist evidence refs not massive prompt content.
6. Record exact merged SHA and notify consumers to resync before they integrate.
