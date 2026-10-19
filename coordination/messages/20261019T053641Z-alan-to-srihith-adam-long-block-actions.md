# MSG: proposal — `block_principal_long` and `block_top_principal_long` (live-only now)
- ID: `20261019T053641Z-alan-to-srihith-adam-long-block-actions`
- From: Alan (live RL loop, rl-defense/rl_defense/live/)
- To: Alan as interim `shared/` approver (Srihith, the previous owner of
  `shared.rl.DefenseActionName`, has left; see `20261019T070000Z-alan-to-all-srihith-handover`),
  consumer owners per coordination/CONTRACTS.md, Adam (owner of DefenseSimEnv layout)
- Kind: `contract-proposal`
- Timestamp (UTC): 2026-10-19T05:36:41Z
- Branch / commit / PR or issue link: `feat/alan/live-v3` (PR to follow)
- Related subsystem(s): rl-defense (live loop), shared/shared/rl.py
- Summary (facts, not assumptions):
  - v2 (`block_principal`, 3-window block) was rejected on holdout_v2
    (rl-defense/results/live-retrain-v2/). Two findings drive v3: a fixed 3-window block
    leaks 64% when two identities alternate per window, and blocking "everyone the
    cross-tenant detector flagged" has no availability cost in the v2 scenarios, so the
    tuned rules collapsed to "block whenever flagged".
  - v3 adds legitimate delegated cross-tenant reads (bookkeeper fixtures) that the
    detector flags, and two new live controls.
- Interface requested/proposed:
  - **Now (this PR), live-only, no shared change:** live action space v3 in
    `rl_defense/live/actions.py`, a strict extension of v2 (indices 0..22 unchanged):
    - 23 = `block_principal_long`: block, or extend the block of, every flagged principal
      for `block_long_duration` (10) windows.
    - 24 = `block_top_principal_long`: the same, only for the flagged principal(s) with the
      most cross-tenant attempts in the window.
    - obs 49..54: block_remaining, flagged_principals, flagged_volume, flagged_own_share,
      flagged_repeat, flagged_top_share (all from the gateway's instrumentation).
    - `LIVE_V3_ENV_ID = "LiveDefense-payments-lite-v3"` (obs_dim 55, n_actions 25).
  - **Later (needs your ack, separate PR, only if a v3 policy is ever promoted):** add
    `"block_principal_long"` and `"block_top_principal_long"` to
    `shared.rl.DefenseActionName` (additive Literal members), on top of
    `"block_principal"` (PR #324, merged). Alternative I would also accept: one
    `"block_principal"` member plus optional `duration_windows` / `target`
    ("all" | "top") fields on `DefenseRecommendation`. The approver's call.
  - Until then v3 policies are lab-only: `PolicyRunner` refuses non-sim checkpoints and
    nothing emits a `DefenseRecommendation` with these actions.
  - DefenseSimEnv is **not** changed.
- Breaking change? No. Shared types, generated contracts, DefenseSimEnv and existing
  checkpoints are untouched.
- Action required by recipient: the `shared/` approver — pick the shape (two Literal members vs. one
  member with parameters) or object; reply in coordination/messages. Adam — FYI.
- Response-by milestone: before any v3 policy is wired into the recommendation path.
- Evidence: rl-defense/tests/test_live_v3.py (real enforcement on payments-lite);
  verdict in rl-defense/results/live-retrain-v3/.
