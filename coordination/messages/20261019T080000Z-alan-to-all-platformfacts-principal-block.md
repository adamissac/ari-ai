# MSG: `PlatformFacts` gains two principal-block fields; v2 policies can be served
- ID: `20261019T080000Z-alan-to-all-platformfacts-principal-block`
- From: Alan (interim `shared/` approver, see coordination/OWNERSHIP.md)
- To: all (Adam: rl-defense; Vihaan: frontend consumers; backend has no named owner)
- Kind: `decision`
- Timestamp (UTC): 2026-10-19T08:00:00Z
- Branch / commit / PR or issue link: `feat/alan/serve-v2-recommendations`
- Related subsystem(s): shared/shared/rl.py, shared/generated, rl-defense (inference, explain, observations)
- Summary (facts, not assumptions):
  - Approved by Alan in the session that made the change (2026-10-19).
  - `PlatformFacts.principal_block_active: bool = False` and
    `PlatformFacts.principal_block_available: bool = False` are added. Both are additive
    with defaults, so existing payloads validate unchanged.
  - `PolicyRunner` now serves `LiveDefense-payments-lite-v2` checkpoints. The obs gains
    feature 48 from `principal_block_active`, and the `block_principal` mask entry comes
    from `principal_block_available`. Recommendations carry a lab-derived caveat. The
    `policy_version` prefix is the checkpoint's env id.
  - Simulator checkpoints behave exactly as before, because the 48-feature obs ignores
    the new fields (tested).
  - The backend builds PlatformFacts from findings and has no principal detector, so the
    fields stay False there. A v2 policy served by the backend never recommends
    `block_principal`.
- Breaking change? No. Generated JSON Schema/TS gain two optional-with-default properties.
- Action required by recipient: none. A future producer that can detect principals should
  set both fields.
- Evidence: rl-defense/tests/test_v2_recommendations.py (6 tests, including the live
  loop's v2 obs being identical to the PlatformFacts mapping).
