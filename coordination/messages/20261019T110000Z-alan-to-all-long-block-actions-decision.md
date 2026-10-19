# MSG: decision — long-block actions enter `shared.rl` (contracts 0.13)
- ID: `20261019T110000Z-alan-to-all-long-block-actions-decision`
- From: Alan (interim `shared/` approver, see coordination/OWNERSHIP.md)
- To: all (Adam: rl-defense; Vihaan: frontend consumers; backend has no named owner)
- Kind: `decision`
- Timestamp (UTC): 2026-10-19T11:00:00Z
- Branch / commit / PR or issue link: `feat/alan/serve-live-v3`. Answers
  `20261019T053641Z-alan-to-srihith-adam-long-block-actions` and addresses #335 and #326.
- Related subsystem(s): shared/shared/rl.py, shared/generated, rl-defense (layouts, inference, explain, observations, live)
- Summary (facts, not assumptions):
  - Trigger: the v6 live candidate is the first to pass the pre-registered gate
    (`recommend_promote`, rl-defense/results/live-retrain-v6/). It is a live_v3 checkpoint,
    and serving it needs these names.
  - The proposal offered two shapes. The chosen one is the first: two additive Literal
    members, `"block_principal_long"` and `"block_top_principal_long"`. They map
    one-to-one to action indices 23 and 24, and existing payloads are unaffected.
  - `PlatformFacts` gains `principal_block_long_available`,
    `principal_block_top_long_available` (bool, default False) and the six detector
    features `block_remaining`, `flagged_principals`, `flagged_volume`,
    `flagged_own_share`, `flagged_repeat`, `flagged_top_share` (float 0..1, default 0).
    Only a principal detector sets them; the live loop's `platform_facts()` does. The
    backend has none, so a v3 policy served there never recommends a block.
  - `SCHEMA_VERSION` 0.12.0 → 0.13.0, also covering #324 and #334 (the bump owed by #335
    and #326).
  - #335 follow-ups in the same change:
    - layout constants are moved to `rl_defense/layouts.py`, so inference needs no
      httpx/starlette;
    - `live/run.py` runs a checkpoint in its own layout;
    - `LIVE_LAB_CAVEAT` no longer claims a training origin;
    - docs are updated;
    - CHANGELOG line added.
- Breaking change? No. All additions are optional with defaults, and generated JSON
  Schema/TS gain only optional properties and enum members.
- Action required by recipient: none. Frontend consumers that switch over
  `DefenseActionName` should handle the two new members. None was found in `frontend/`.
- Evidence: rl-defense/tests/test_v3_recommendations.py (9 tests),
  test_v2_recommendations.py (unchanged, passing), `make check` (contracts fresh),
  backend/tests/test_rl_integration.py.
