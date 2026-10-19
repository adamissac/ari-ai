# MSG: decision — runtime principal counters (contracts 0.14, ADR-0017)
- ID: `20261019T200000Z-alan-to-all-runtime-principal-counters`
- From: Alan (interim `shared/` approver)
- To: all (Adam: rl-defense; Vihaan: frontend consumers; backend has no named owner; monitoring reporters)
- Kind: `decision`
- Timestamp (UTC): 2026-10-19T20:00:00Z
- Branch / commit / PR or issue link: `feat/alan/runtime-principal-detector`
- Related subsystem(s): shared/shared/monitoring.py, shared/shared/rl.py, backend (runtime ingest, rl_recommend), rl-defense (platform_mapping, live/report.py)
- Summary (facts, not assumptions):
  - `RouteWindow.principals: list[PrincipalCounts]` (optional, default empty). Each entry
    carries `principal` (a `PrincipalRef`, pattern `^prn_[A-Za-z0-9_-]{4,64}$`,
    pseudonymous) and the counts `cross_tenant`, `delegated` and `own`. Validation: no
    duplicate principals, and counts ≤ the route's requests.
  - `DefenseRecommendation.principal_targets: list[PrincipalRef]` (default empty), filled
    for block actions.
  - `SCHEMA_VERSION` 0.13.0 → 0.14.0.
- Breaking change? No. Additive with defaults: existing reporters and payloads validate
  unchanged.
- Action required by recipient: a reporter that can see token principals and object owners
  should send pseudonymous counters. Reference: `rl_defense.live.report`. Frontend: the
  recommendation panel can show `principal_targets` (pseudonyms only).
- Evidence: rl-defense/tests/test_principal_detection.py, backend/tests/test_runtime_ingest.py,
  backend/tests/test_rl_integration.py.
