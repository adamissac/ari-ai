# MSG: RL-CMDP-003 owned-app request-context checks

- From: alan
- To: all
- Kind: implementation / evidence
- Timestamp (UTC): 2026-10-23T05:58:28Z
- Branch: `feat/alan/read-context-integration`
- Scope: opt-in `rl-defense/rl_defense/research/payment_read_lab.py`, wrapping the actual owned payments-lite fixture. No original example edits, public/shared contract changes or serving hook.
- Evidence: eight real-app integration tests pass, including original BOLA before/after, own/exact delegated reads, request binding, current permissions, serialized revocation and buffered expiry/timeout/body bounds.
- Limits: one private in-memory store and one asyncio lock; outside writers and multiple workers unsupported. This does not duplicate PR #393's operational control lifecycle.
- Next: CI/review; no training, holdout replay, prior comparison rerun, model promotion or customer enforcement.
