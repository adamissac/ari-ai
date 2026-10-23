# MSG: Live Defense Phase 4 contracts 0.18.0 (owned-test enforcement)

- ID: `20261023T051200Z-alan-to-all-live-defense-phase4-contracts`
- From: alan
- To: all
- Kind: `integration`
- Timestamp (UTC): 2026-10-23T05:12:00Z
- Branch / commit / PR or issue link: `feat/live-defense-phase4-controlled-enforcement` (PR opened from this branch; do not auto-merge)
- Related subsystem(s): `shared/`, `backend/`, `frontend/`, Live Defense
- Summary (facts, not assumptions): Phase 4 adds additive `shared` 0.18.0 types (`LiveControl`, `ControlGrant`, `ControlChannel*`, `ControlAuthorizationCreate`, `EmergencyStop`) and Alembic `0012`. Analyst review and `LivePolicyDecision.enforcement=NOT_EXECUTED` are unchanged. Executable actions exist only after `authorize.check` against a registered loopback owned-test app. Codex/`rl-defense/` untouched. Phase 5 autonomous / production not started.
- Interface requested/proposed (field-level types/example payload):
  - `POST /applications/{id}/control-authorizations` body `ControlAuthorizationCreate` `{kind, target:{type,value}, duration_s, rationale, live_policy_decision_id, max_requests}` — session identity only; extra `usr_*` fields 422
  - `POST /applications/{id}/control-channel` `{port}` — HMAC shown once
  - `POST /projects/{id}/control-grants` `{application_id, allowed_kinds, max_duration_s, hourly_budget, expires_at}`
  - `GET /projects/{id}/live-controls` labelled OWNED TEST ENVIRONMENT
- Breaking change? migration/test impact: Additive. Migration 0012 is the new Alembic head. Consumers must regenerate from `shared/generated`.
- Action required by recipient: Srihith — contract ack. Vihaan — frontend types already wired on this branch. Codex — no RL action. Security/Alan review before merge (executable-action trust boundary).
- Response-by milestone (not invented clock time): before merging this PR
- Evidence: `docs/LIVE_DEFENSE_PHASE4_EVAL.md`; 20 owned-fixture scenarios in `backend/tests/test_live_defense_phase4.py`
- In-Reply-To:
