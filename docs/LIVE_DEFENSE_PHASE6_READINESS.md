# Live Defense Phase 6 — post-merge integration audit and shadow-pilot readiness

Status: **observed on `feat/live-defense-phase6-pilot-audit` from live `origin/main`**.
This is not customer-production evidence, not a claim that shadow mode prevented
breaches, and not authorization to start Phase 7 or autonomous RL enforcement.

**Verdict for one company-owned staging app in recommendation-only shadow mode:
CONDITIONAL GO.**

The control plane on current main can record ingest, persist
`LivePolicyDecision` rows as `NOT_EXECUTED`, take analyst opinions, and export a
pilot report without creating `LiveControl` rows or `live_defense_execute` jobs.
That holds even when an owned-test grant and loopback channel already exist on
the same application. It does **not** mean a customer may use the Controls tab,
register a grant, or point Ari at a third-party host.

## Live GitHub (do not trust stale handoffs)

Checked with `gh pr view` and `git fetch origin main` during this session.

| Fact | Observed |
|---|---|
| `origin/main` SHA | `02ab34deb68059b8dcff0856724593340022776a` (merge of PR #409) |
| PR [#393](https://github.com/adamissac/ari-ai/pull/393) | **MERGED** 2026-10-23T10:05:12Z by `adamissac` as `57e0326309d5630c5f3b10d1af3fe91c507d0972` |
| PR [#395](https://github.com/adamissac/ari-ai/pull/395) | **MERGED** 2026-10-23T06:31:51Z as `8bbc01e2729757aff40bc7a7745d764bb90dccd0` |
| `SCHEMA_VERSION` | `0.19.0` (`shared/shared/__init__.py`) |
| Alembic heads | single head `0014` (`test_repository_has_a_single_migration_head`) |
| Codex / v6 / datasets | not trained, promoted, or edited in this work |

Phase 4 owned-test controls and Phase 5 shadow-pilot readiness are **both on
main**. That is the integration fact this audit exists to prove.

## Paths (shadow vs enforcement)

```
SHADOW (recommendation-only)
  owner enables monitoring_policy
    → register staging app (sandbox | owned_test; shadow_mode always true)
    → issue / rotate ingest token (secret shown once; SHA-256 stored)
    → POST /ingest/runtime/{project_id} (Bearer)
    → anomaly MonitoringEvent / finding correlation
    → job live_defense_shadow (idempotent)
    → LivePolicyDecision { enforcement: NOT_EXECUTED, executed: false }
         producer: rules | v6_shadow | abstention
    → analyst accept/reject (executes: false)
    → GET /projects/{id}/pilot-report
    → disconnect → further ingest 401

ENFORCEMENT (owned-test only; not the shadow-pilot)
  owner grant + loopback control channel
    → POST /applications/{id}/control-authorizations (session owner)
    → authorize.check (15 checks, fail closed)
    → LiveControl authorized
    → job live_defense_execute → HMAC adapter 127.0.0.1:{port}/live-defense/control
    → verify / expire / rollback / emergency-stop
```

Review ≠ authorize ≠ execute ≠ verify. A `LivePolicyDecision` has no transition
into `executing`. v6 and rules may propose; they cannot skip the gate.

### Accidental interaction points

| Interaction | Expected | Actual after this audit | Severity |
|---|---|---|---|
| Grant + channel present during ingest | Shadow must not auto-execute | `live_defense_shadow` still only writes `LivePolicyDecision`; zero `live_defense_execute` jobs; fixture `ControlPlane.controls` empty | P0 if broken; **proven held** |
| Analyst accept on a live decision | Opinion only | HTTP 201, `executes=false`, control count unchanged | Proven held (Phase 3/4/6) |
| Worker retry of the same window | Idempotent shadow | Second `live_defense_shadow` job, still 1 decision, 0 controls | Proven held |
| Pilot report export | No execute | Report `shadow_mode=true`; unsupported claims listed; no execute jobs | Proven held |
| Disconnect then authorize leftover grant | Must not apply | Gate denies `application_registered` ("Application is disconnected."); execute TOCTOU rejects an already-authorized control | **P1 found and fixed** |
| Controls tab in the same UI | Separate owned-test path | Still present; labelled separate. Shadow-pilot procedure forbids using it | Residual operational P1 |
| `x-ari-source` | Fixture probe header, not production identity | Unchanged; not used on the shadow path | Owned-test residual |
| HMAC secret in `control_channels` | Shown once on create | List/audit omit it; column remains plaintext (owned-test only) | Residual P2 if a customer registers a channel |

## Integration matrix

| Surface | Expected | Actual on `02ab34de` + this branch | Evidence | Tests | Gap | Sev |
|---|---|---|---|---|---|---|
| Monitoring enable | Does not arm an enforcer | `monitoring_policy.enabled` only queues repo re-checks | API | phase6 shadow lifecycle uses `setup_project(..., enabled=True)` | none for shadow | — |
| Staging registration | sandbox / owned_test; never production | `StagingEnvironment` enum; `shadow_mode: Literal[True]` | contract + API | phase5/6 | no customer-staging environment value (intentional) | — |
| Ingest auth / schema / tenant | Bearer token; other org 404 | SHA-256 stored; outsider 404 | DB + API | phase6 credential + tenant tests | none | — |
| Finding / anomaly | Recorded, not executed | ingest 202 with `anomalies >= 1`; events listed | API | phase6 | HTTP 200 is not IDOR | — |
| `LivePolicyDecision` | `NOT_EXECUTED` | persisted; Q-values null unless inference ran | API/DB | phase3 + phase6 | this env: v6 `skipped_unavailable` (`rl_defense` not installed) | P2 honesty |
| Frozen v6 | Hash pin; refuse mismatch | `_load_v6` raises `ValueError` on hash mismatch before `PolicyRunner` | unit | `test_frozen_v6_hash_mismatch_refuses_load` | serving with torch not re-run here | — |
| Rules producer | Suggests; does not execute | producer in `{rules, v6_shadow, abstention}` | API | phase3/6 | — | — |
| Analyst accept | `executes=false` | 201; no execute jobs | API/DB | phase3 s05, phase6 | — | — |
| Pilot report | Honest caveats | `unsupported_claims` include “shadow prevented breaches” | API | phase5/6 | — | — |
| Worker retries | Shadow idempotent; failures visible | retry keeps 1 decision; poison job `last_error` on `GET /jobs/{id}` and report trail; health stays `unknown` | API/DB/worker | phase6 | no project-wide failed-job list besides the trail | P2 |
| Queue depth | Measured, tenant-scoped, not a verdict | counted only for `payload.project_id`; other tenant queued jobs are 0 | API | `test_queue_depth_is_project_scoped_not_other_tenants` | `worker_seen_at` remains process-global heartbeat | P2 |
| Health / graph | Never optimistic healthy | `status/worker/telemetry/policy = unknown`; graph never `healthy` | API | phase5/6 | no health-check producer | — |
| Owned-test enforcement | Loopback fixture only | 15 checks, allowlist, grant, TTL, kill switch, SSRF, HMAC, TOCTOU, concurrency, revocation, idempotency re-validated | API + fixture HTTP | phase4 + authorize + owned_test_app | production still denied | — |
| Customer-staging (non-fixture) | Likely none | **none exercised**; third-party hosts forbidden | — | — | one real company app not connected in this session | condition |

Simulation vs owned-test HTTP vs shadow vs approved controls vs customer-staging:

| Lane | What it is | Used in a shadow-pilot? |
|---|---|---|
| Gym / simulator scores | Research metrics | No. Not live proof. |
| Owned-test HTTP fixture | `127.0.0.1` HMAC adapter | No, unless the owner separately authorizes. Forbidden in shadow-pilot procedure. |
| Shadow | Ingest → decision → review → report | Yes. Recommendation-only. |
| Approved owned-test controls | Gate + adapter | Separate path on main. Not shadow-pilot. |
| Customer-staging (company-owned) | Authenticated `owned_staging` ingest | Intended target of CONDITIONAL GO. Not a third-party system. Not exercised live here. |

## Highest-priority proof: shadow cannot execute

`backend/tests/test_live_defense_phase6.py::test_shadow_path_does_not_execute_with_grant_channel_v6_rules_accept_retries_report`
ran against real PostgreSQL, the FastAPI app, and the SKIP LOCKED worker.

Setup: monitoring on, owned_test app, ingest token, **grant + loopback channel
bound to a fixture that records applied controls**.

Then: authenticated ingest (finding/anomaly) → drain `live_defense_shadow` **and**
all execute/verify/rollback/expire/stop kinds → accept + needs_investigation →
re-enqueue shadow for the same window → export report.

Observed:

- `LivePolicyDecision.enforcement == NOT_EXECUTED`, `executed is False`
- `AnalystReview.executes is False`
- `_control_count == 0`
- `live_defense_execute` absent from the project's jobs
- fixture `ControlPlane.controls == {}` (no adapter apply)
- health statuses `unknown`
- graph has no `healthy` observation
- outsider 404 on the report and decision list

## Fixes in this slice (smallest diffs)

1. **P1 disconnected leftover grant.** `authorize.check` now fails
   `application_registered` when `disconnected_at` is set (still 15 named checks;
   not an allowlist expansion). Execute re-gates, so disconnect-after-authorize
   rejects and does not call the adapter
   (`test_disconnected_app_cannot_authorize_or_execute_leftover_grant`,
   `test_disconnect_after_authorize_blocks_execute_toctou`).
2. **P1 queue-depth tenant mix.** `DefenseHealth.queue_depth` counts queued jobs
   whose `payload.project_id` matches; other tenants' work is not shown as this
   project's depth.
3. **P2 worker-failure visibility.** Failed/dead/errored live-defense jobs for
   the project appear on the pilot-report investigation trail; `GET /jobs/{id}`
   returns `last_error` (no trace) to the owning tenant; health stays `unknown`.
4. **Copy.** Dashboard states recommendation-only shadow vs the separate
   Controls path. Queue depth is labelled “this project”.

No new executable action. No production grant. No autonomous RL. No Phase 7.
`AUTHORIZATION_CHECKS` remains length 15.

## Proposed owner acceptance gates (not invented SLAs)

Owner-chosen. Suggested abort conditions for a shadow-pilot window:

| Gate | Propose | Not a claim |
|---|---|---|
| Execute jobs | `live_defense_execute` count stays 0 | Not an availability SLO |
| Controls | `LiveControl` count stays 0 | — |
| Decisions | every row `enforcement=NOT_EXECUTED` | Not “attacks blocked” |
| Reviews | every accept `executes=false` | Not an RL label |
| Health | statuses remain `unknown` unless a real health producer is added later | HTTP 200 ≠ healthy |
| Credentials | token shown once; rotate/disconnect 401s the old secret | — |
| Scope | no control-grant, no control-channel, no Controls tab use | — |
| Target | company-owned staging only; no third-party hosts | — |

If any execute job or `LiveControl` appears, abort the pilot and treat the
install as out of shadow mode.

## Commands actually run

```
make check
  ruff pass; format 184 files; shared.export --check 140 files; examples check pass

uv run mypy
  Success: no issues found in 40 source files (shared/monitoring/standards)

uv run pytest -q backend/tests/test_live_defense_phase6.py \
  backend/tests/test_live_defense_authorize.py \
  backend/tests/test_live_defense_phase4.py \
  backend/tests/test_live_defense_phase5.py \
  backend/tests/test_live_defense_phase3.py \
  backend/tests/test_live_defense_pilot.py \
  backend/tests/test_owned_test_app.py \
  shared/tests/test_contracts.py \
  backend/tests/test_parallel_migrations.py
  149 passed, 1 skipped (TSC unset) in 26.32s

npm run lint --prefix frontend        pass
npm run typecheck --prefix frontend   pass (after transport build)
npm test --prefix frontend            330 passed / 78 files
npm test --prefix frontend/transport  35 passed
```

Skipped / not run in this session:

- Playwright e2e stack (`frontend/tests/e2e/stack.py`) — not executed here;
  API/DB/worker tests are the proof. Screenshots are not the evidence.
- Live Claude / `RUN_LIVE_LLM_EVAL`
- Docker sandbox CI job
- Frozen v6 *inference ran* (no `rl_defense`/torch in this workspace install;
  hash-mismatch refuse-to-load was tested)
- Training, promotion, dataset, or Codex research edits
- Ingest from a hosted company staging app or any third-party system
- `gitleaks` binary not installed in this environment

## Customer-facing procedure

See [LIVE_DEFENSE_SHADOW_PILOT.md](LIVE_DEFENSE_SHADOW_PILOT.md).

## Next priorities (not this PR)

1. Hosted ingest of **one company-owned** staging app under the procedure above.
2. Deploy path that can load frozen v6 (or keep explicit `skipped_unavailable`).
3. Decide whether the Controls tab should be hidden unless an owner grant exists
   (operational P1; would not expand enforcement).
4. Hash-at-rest for control-channel HMAC secrets (owned-test residual).
5. Do **not** start Phase 7 / autonomous RL enforcement.
