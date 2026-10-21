# Alan → all: v10 diagnosis and validation-only guard

### 2026-10-21 — RL-DIAG-001: targeted v10 diagnosis (Alan, owner authorized)

IN_PROGRESS `feat/alan/rl-targeted-diagnosis`. All ten selected checkpoints already
miss85% validation availability; rotation exposes principal-block collateral cost,
not token-rotation bypass. Added saved-data/input-pinned diagnostics and opt-in
`--require-validation-availability` rejection before any holdout policy execution.
Targeted gateway regressions preserve own/delegated access assertions and prove the
current broad-control tradeoff. No new training/holdout replay or promotion. V6 stays
deployed. No v11 launch: process guard is not proof of a better learned policy.

Focused verification: 22 tests passed in 22.51s, including the unchanged complete v10
evidence bundle. Ruff lint/format and diff checks pass. No new policy execution or
training performed by this diagnosis. Full CI and review pending.
