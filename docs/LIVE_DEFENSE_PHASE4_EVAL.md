# Live Defense Phase 4 — owned-test enforcement evaluation

Status: **observed on `feat/live-defense-phase4-controlled-enforcement`**.
This is **not** customer-production evidence and **not** a claim that
Gym/simulator metrics transferred to live control. There is no untreated
production arm. Controls ran only against a repo-owned loopback fixture.

Base: `origin/main` `5be62de` (Phase 3 PR #392), later merged `09e8cab`
(Codex constrained-RL Phase 1). Authorization decision is **ADR-0020**
(ADR-0019 on main is Codex's RL foundation).
Codex owns RL research: this branch does not train, promote, or edit v6
weights, datasets, or the promotion registry. RL files on this branch exist
only via merge of `origin/main`.

## What was exercised

Authorized owner inspects a staged finding / shadow decision (Phase 3 path
unchanged) → separate `POST /applications/{id}/control-authorizations` →
15-check fail-closed `authorize.check` → `LiveControl` `pending_authorization`
→ `authorized` (never jumps to `executing`) → existing SKIP LOCKED worker
`live_defense_execute` HMAC adapter to `http://127.0.0.1:{port}/live-defense/control`
→ `live_defense_verify` with **real HTTP probes** (adapter HTTP 200 is not
effectiveness) → dashboard labelled **OWNED TEST ENVIRONMENT** → rollback /
app-local TTL / emergency stop.

Review, authorization, execution, and verification stay distinct operations.

## Observed metrics

| Metric | Sample | Result | Notes |
|---|---|---|---|
| s01 request-scoped rate limit | n=1 owned fixture | `verified`; probes include 429 | `test_s01_rate_limit_authorized_enforced_and_verified` |
| s02 exact-source block (198.51.100.66 only) | n=1 | `verified`; probes include 403 | `test_s02_exact_source_block_fixture_ip` |
| Overnight A public/malformed block | public `8.8.8.8`, TEST-NET-3, CIDR, spaces, IPv4-mapped | denied by gate **and** adapter | `test_public_private_malformed_and_protected_sources_denied`, `test_public_unicast_block_rejected_by_authz_and_adapter` |
| Overnight B idempotent integrity | same-id retry mutated kind/rate | HTTP 409, original binding kept; concurrent same payload 1 apply + 7 idempotent | `test_idempotent_retry_conflict_does_not_mutate`, `test_concurrent_same_payload_stays_single_control`, `test_stale_retry_with_mutated_binding_is_conflict` |
| Overnight C logging restore | expiry/rollback/kill-switch/restart/overlap | prior `info` restored; overlap stays debug until last | `test_increase_logging_expiry_rollback_and_kill_switch_restore_prior`, `test_logging_ttl_without_worker_restores_prior` |
| Overnight D `x-ari-source` | spoofed public / tenant label | ignored unless owned-test probe IP | `test_x_ari_source_is_fixture_probe_header_not_production_identity` |
| Grant revoke TOCTOU | authorize then revoke then execute | control `rejected` | `test_grant_revoke_blocks_execute_toctou` |
| Hourly budget + grant lock | budget=1, two escalate | second HTTP 403 | `test_hourly_budget_serializes_under_grant_lock` |
| HMAC body+id | tampered JSON, original signature | HTTP 401 | `test_hmac_covers_body_digest_and_control_id` |
| s03 increase logging | n=1 | `verified` | `test_s03_increase_logging` |
| s04 escalate to human (no adapter) | n=1 | `verified`; method `recorded_escalation` | `test_s04_escalate_records_without_adapter` |
| s05 Phase 3 accept still non-executing | n=1 accept on real `LivePolicyDecision` | `executes=false`; live-control count unchanged | `test_s05_phase3_accept_still_does_not_execute` |
| s06 recommendation cannot jump to EXECUTING | n=1 transition | `IllegalControlTransition` | `test_s06_recommendation_cannot_jump_to_executing` |
| s07 rules/analyst proposal without grant | n=1 | HTTP 403 `LIVE_CONTROL_DENIED`; status rejected/escalated | `test_s07_rules_proposal_without_grant_is_denied` |
| s08 `usr_*` in body is not identity | n=1 extra `actor_id` | HTTP 422 | `test_s08_usr_star_in_body_is_not_identity` |
| s09 CIDR rejected | n=1 `198.51.100.0/24` | HTTP 403 | `test_s09_cidr_rejected` |
| s10 loopback block rejected | n=1 `127.0.0.1` | HTTP 403 | `test_s10_loopback_block_rejected` |
| s11 principal-wide target rejected | n=1 application/`prn_*` | HTTP 403 | `test_s11_principal_wide_target_rejected` |
| s12 HTTP 200 ≠ unauthorized / ≠ effectiveness | n=1 verified control | `adapter_http_200_is_not_effectiveness=true` | `test_s12_http_200_is_not_treated_as_unauthorized` |
| s13 SSRF / arbitrary URLs | 5 URLs | `AdapterDenied` | `test_s13_ssrf_arbitrary_urls_denied` |
| s14 HMAC replay | n=1 duplicate nonce | second POST 401 | `test_s14_hmac_replay_rejected` |
| s15 idempotent control id | n=2 apply | second `idempotent=true` | `test_s15_idempotent_control_id` |
| s16/s17 verify-fail rollback + unresolved blocks | n=1 wrong route | failed/rolled_back/escalated; further authorize 403 when unresolved | `test_s16_*`, `test_s17_*` |
| s18 app-local TTL without worker | n=1 1s expiry | 429 then 200/200 after expiry | `test_s18_ttl_expires_on_the_app_without_worker` |
| s19 emergency stop | n=1 | `verified_cleared=false` until worker; new authorize 403 | `test_s19_emergency_stop_rejects_new_and_does_not_claim_until_verified` |
| s20 no browser-callable bypass | OpenAPI POST paths | no `/isolate` `/apply` `/rate-limit` `/block`; authorize + emergency-stop present | `test_s20_no_browser_callable_bypass_routes` |
| Tenant isolation | outsider org | 404 on list | `test_tenant_isolation_on_controls` |
| Member cannot authorize | member role | 403 | `test_member_cannot_authorize` |
| End-to-end owned-test UI | 1 Playwright run, real API+Postgres+worker+`next start` | 1 passed (5.1s) then 2 passed with Phase 3 (14.4s) | `live-defense-phase4.spec.ts`, `live-defense.spec.ts` |

Gym / held-out RL scores were **not** reused as live-control proof.

### Test commands (executed)

```
make check
  ruff pass; format 175 files; shared.export --check 137 files; examples check pass

uv run mypy
  Success: no issues found in 40 source files

uv run pytest -q backend/tests/test_parallel_migrations.py shared/tests/test_contracts.py \
  backend/tests/test_live_defense_phase4.py backend/tests/test_live_defense_authorize.py
  100 passed, 1 skipped (TSC unset)

uv run pytest -q backend/tests/test_live_defense_phase4.py backend/tests/test_live_defense_authorize.py \
  backend/tests/test_live_defense_phase3.py
  44 passed

npm run lint --prefix frontend && npm run typecheck --prefix frontend
  pass

npm test --prefix frontend
  327 passed / 77 files

npm test --prefix frontend/transport
  35 passed

npm run build --prefix frontend
  pass; routes include /live-defense/controls and /live-defense-pilot/controls

cd frontend && E2E_SKIP_BUILD=1 E2E_BROWSER_CHANNEL=chrome ../.venv/bin/python tests/e2e/stack.py \
  tests/e2e/live-defense.spec.ts tests/e2e/live-defense-phase4.spec.ts
  2 passed (14.4s) — Chromium, real stack, provider_mode=fake for unrelated LLM paths
```

`git diff origin/main -- rl-defense` is empty. No training run, no checkpoint
write, no promotion.

## Unavailable / not measured

| Claim | Why unavailable |
|---|---|
| Production compromise reduced | No customer production grant; no production environment value |
| Autonomous enforcement | Phase 5; gate still requires owner session |
| Frozen-v6 as executor | v6 may propose via shadow origin; it cannot skip the gate |
| Isolation / credential rotation / prod firewall / code deploy / DB mutation / auto-patch | No adapters |
| Time-to-contain on a customer staging fleet | Only the owned loopback fixture |
| Simulator availability / compromise rates as live proof | Gym metrics are simulation-derived; they are not this eval |
| Health as a liveness verdict | `DefenseHealth.status` remains `unknown` |

## Before / after (this slice)

| Surface | Before (Phase 3 on main `5be62de`) | After (Phase 4) |
|---|---|---|
| Analyst accept | Recorded opinion, `executes=false` | Unchanged |
| Executable action | None | Four kinds on owned-test loopback after gate |
| Lifecycle | NIST incidents + shadow `LivePolicyDecision` | Separate `LiveControl` statuses |
| Adapter | None | HMAC, replay window, idempotent control id, SSRF-safe loopback |
| UI | Overview / Investigation / Explain / Apps | + Controls; authorize is a separate form |

## Demo commands

```
python scripts/live_defense_phase4_demo.py --print
OWNED_TEST_HMAC_SECRET=hkt_ctl_... uv run python -m backend.live_defense.owned_test_app --port 8099
```

## Limitations

- Fixture is loopback-only. Browser-supplied destinations are rejected.
- Exact-source block allows **only** RFC 5737 TEST-NET-2 `198.51.100.66`.
  Public unicast is denied (overnight fix; previously `address_policy` treated
  globally-routable unicast as allowed).
- `x-ari-source` is a fixture probe header, not production attribution.
- Idempotent apply refuses binding changes (kind/target/duration/expiry/rate).
- `increase_logging` restores the prior log level on expiry, rollback,
  kill-switch, and fixture restart.
- Worker must be running to apply/verify; TTL still expires on the app if the worker dies.
- Emergency stop records the attempt and does not claim success until verified.

## Customer-pilot blockers

- Hosted owned-test app that is not 127.0.0.1 (would need a new allowlist ADR)
- Production `StagingEnvironment` value (explicitly rejected)
- Autonomous mode (Phase 5)
- Human security review of this authorization trust-boundary change

## Phase 5 recommendations (do not implement here)

1. Keep the gate as final authority; do not let v6 Q-values authorize.
2. Require a second human for any environment broader than owned-test.
3. Add independent verification that cannot share the execute sandbox.
4. Do not overload NIST incident statuses.
5. Kill switch must remain fail-closed and must not report success on adapter HTTP 200.

## Screenshots (owned-test, not sample-as-live)

- `/cursor/stores/self/media/live-defense-phase4/owned_test_verified_control.png`
- `/cursor/stores/self/media/live-defense-phase4/owned_test_rollback_and_kill_switch.png`
- `/cursor/stores/self/media/live-defense-phase4/owned_test_staging_apps.png`
