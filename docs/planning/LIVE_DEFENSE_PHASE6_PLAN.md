# Live Defense Phase 6 plan — post-merge audit (no Phase 7)

Status: **audited and hardened** on `feat/live-defense-phase6-pilot-audit`
from live `origin/main` `02ab34de`. This is verification of Phase 4 (#393) +
Phase 5 (#395) together. It does **not** start Phase 7 or autonomous RL.

Codex owns RL research. This work does not train, promote, or edit v6 weights,
datasets, or the promotion registry.

## Goal

Prove, with API/DB/worker evidence on current main, whether one company-owned
staging app can evaluate Ari in **recommendation-only shadow mode** without
accidental execution now that owned-test controls also live on main.

## Explicit non-goals

- Phase 7 / autonomous enforcement
- Training, promotion, or dataset edits
- Expanding owned-test allowlists or production grants
- Testing third-party systems
- Declaring readiness because tests exist

Eval: [LIVE_DEFENSE_PHASE6_READINESS.md](../LIVE_DEFENSE_PHASE6_READINESS.md).
Customer procedure: [LIVE_DEFENSE_SHADOW_PILOT.md](../LIVE_DEFENSE_SHADOW_PILOT.md).
