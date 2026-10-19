# MSG: proposal — `block_principal` defense action (live-only extension now, shared later)
- ID: `20261019T043718Z-alan-to-srihith-adam-block-principal-action`
- From: Alan (live RL loop, rl-defense/rl_defense/live/)
- To: Srihith (owner of `shared.rl.DefenseActionName`), Adam (owner of DefenseSimEnv layout)
- Kind: `contract-proposal`
- Timestamp (UTC): 2026-10-19T04:37:18Z
- Branch / commit / PR or issue link: `feat/alan/live-block-principal` (PR to follow)
- Related subsystem(s): rl-defense (live loop, DefenseSimEnv), shared/shared/rl.py
- Summary (facts, not assumptions):
  - The v1 live-retrained candidate was rejected (rl-defense/results/live-retrain/REPORT.md):
    availability 0.76 < 0.85. The only containment controls are node-level (`isolate`,
    `rate_limit` on `payments`), and both block every legitimate payments request while an
    attack is running (~45% of windows).
  - The live gateway already knows who is attacking: its instrumentation flags a request
    as cross-tenant when the bearer token's principal differs from the object's owner.
  - A principal-scoped control (block the flagged principal on the node where it was
    flagged, for a fixed duration) can contain the BOLA abuse while other tenants' traffic
    keeps flowing.
- Interface requested/proposed:
  - **Now (this PR), live-only, no shared change:** `rl_defense/live/actions.py` defines a
    *live action space v2*: the 22 DefenseSimEnv actions unchanged at the same indices, plus
    index 22 = `block_principal` (global, no node argument; targets the principals flagged
    in the previous window). Observation v2 = the 48 DefenseSimEnv features unchanged plus
    one global feature `principal_block_active` (index 48). `LIVE_V2_ENV_ID =
    "LiveDefense-payments-lite-v2"` in checkpoint manifests (obs_dim 49, n_actions 23).
    Sim-trained 22/48 checkpoints keep loading unchanged; the loop only emits v2 shapes
    when asked (`LoopConfig.action_space="live_v2"`), so v1 runs reproduce exactly.
  - **Later (needs your ack, separate PR):** add `"block_principal"` to
    `shared.rl.DefenseActionName` (additive Literal member) so a v2 policy's
    recommendations can be expressed in `DefenseRecommendation`. Until then, v2 policies
    are lab-only and never emit a `DefenseRecommendation` with that action.
  - DefenseSimEnv (N_ACTIONS=22, OBS_DIM=48) is **not** changed; the simulator has no
    notion of principals. Adding it there is a separate design question for Adam.
- Breaking change? No. Shared types, generated contracts, DefenseSimEnv and existing
  checkpoints are untouched. Additive Literal member later = non-breaking for producers;
  consumers with exhaustive matches on DefenseActionName would need a new arm.
- Action required by recipient: Srihith — ack or object to the additive
  `DefenseActionName` member (reply in coordination/messages). Adam — FYI; say if you
  want the action in DefenseSimEnv.
- Response-by milestone: before any v2 policy is wired into the backend recommendation path.
- Evidence: rl-defense/tests/test_live_block_principal.py (real enforcement on
  payments-lite); verdict in rl-defense/results/live-retrain-v2/ once the run lands.
