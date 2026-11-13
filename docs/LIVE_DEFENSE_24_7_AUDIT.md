# Live Defense: what 24/7 production operation needs

Date: 2026-11-13. Audited `main` at `5d5c26f9`. Paths are under `backend/backend/` unless
they start with another top-level directory.

## Summary

Live Defense today is a shadow recorder plus a human-operated control fixture. It ingests
counters, runs rules, records what it would recommend, and never acts on its own. A human
owner can apply four control kinds, but only to a fixture on `127.0.0.1` in an
`owned_test` or `sandbox` application. No code path lets Ari change a production system,
and a production application cannot even be registered.

Three things stand between this and a real 24/7 defense: there is no telemetry collector,
there is no way to reach a customer system, and there is no RL policy that passed its own
promotion gate. The second and third are owner decisions, not missing code.

## Stage status

| Stage | Implemented | Tested | In production | Evidence |
|---|---|---|---|---|
| Signal ingestion | Yes: `POST /ingest/runtime/{project_id}` with per-app tokens, secret quarantine, rate limit | Yes | Reachable, but nothing sends to it. The only sender is a `curl` snippet in the UI | `api/runtime.py:380-406`, `frontend/lib/live-defense.ts:316`, `backend/README.md:31` ("No production telemetry source") |
| Detection | Yes: per-route anomaly score plus deterministic rules | Yes | Runs on every authenticated batch | `api/runtime.py:333-347`, `live_defense/engine.py:90-98` |
| RL decision | Shadow only. Frozen v6 runs when the source is authenticated, the window is under 30 minutes old, not quiet, and ownership is verified. Otherwise it abstains and rules stand | Yes, where torch is installed | Never ran: the image did not contain the checkpoint, so every eligible window abstained as `skipped_unavailable` (fixed in this PR) | `live_defense/policy.py:84-129`, `backend/Dockerfile` |
| Action execution | Yes, for `rate_limit`, `block_source`, `increase_logging`, `escalate`. Only an owner's API call enqueues it | Yes (30 tests against the fixture) | Unusable: the adapter only talks to `127.0.0.1` | `api/live_defense_controls.py:341`, `live_defense/controls.py:360`, `live_defense/adapters.py:18` |
| Verification | Yes: probes the fixture route after apply; adapter HTTP 200 is not treated as proof | Yes | Fixture only | `live_defense/verify.py:19,41` |
| Rollback, expiry, emergency stop | Yes | Yes | Fixture only. Two rollback bugs fixed in this PR | `live_defense/controls.py:569-693` |

The first-responder layer (Scout and Diagnose on a suspicious window) is implemented and
defaults to OFF per project (`live_defense/modes.py:53-54`). It investigates and
recommends; its decision record always carries `executed: false`
(`live_defense/first_responder.py:747`).

## Tests run

- `uv run pytest -q backend/tests/live_defense_e2e`: 54 passed, 1 skipped (live LLM is opt-in).
- `uv run pytest -q backend/tests -k "live_defense or pilot" --ignore=backend/tests/live_defense_e2e`:
  223 passed, 4 skipped before the change; 226 passed, 4 skipped after.
- One skip matters: `backend/tests/test_rl_integration.py` skips because `rl_defense` is
  not importable in the workspace environment. The v6 inference path is therefore not
  exercised by the default test run.

## Everything that keeps it recommendation-only

1. **Shadow job cannot act.** `live_defense_shadow` only writes a `LivePolicyDecision`
   with `enforcement: NOT_EXECUTED` (`live_defense/engine.py:1-8, 160-177`).
2. **Environment check.** Only `owned_test` and `sandbox` pass; the enum has no
   production value (`live_defense/authorize.py:167-178`, `shared/shared/live_defense.py:56-60`).
3. **Loopback-only channel.** Host must be `127.0.0.1`, checked at the gate and again in
   the adapter (`live_defense/authorize.py:287-302`, `live_defense/adapters.py:35-57`).
4. **Fixture-only source block.** `block_source` accepts only the fixture IP
   (`live_defense/authorize.py:269-284`).
5. **Unsafe kinds denied.** `isolate`, `block_principal*`, `credential_rotation`,
   `firewall`, `deploy`, `db_mutation`, `patch`, `disable_application`
   (`live_defense/authorize.py:31-44`).
6. **Owner grant required.** Exact kind, exact application, duration and hourly budget
   (`live_defense/authorize.py:181-222`).
7. **Session identity only.** Owner role, never a typed actor id
   (`api/live_defense_controls.py:280`, `live_defense/authorize.py:127-136`).
8. **RL-gated pilot apps are shadow-only** at the API, the gate and the worker
   (`live_defense/pilot_guard.py`, `live_defense/authorize.py:156-161`,
   `live_defense/controls.py:379-393`).
9. **AUTO-EXECUTE is rejected**, not implemented (`live_defense/orchestrator.py:246-252`).
10. **First-responder mode defaults to OFF** (`live_defense/modes.py:53-54`).
11. **`PILOT_RECOMMENDATION_ONLY`**: on by default in staging only; preflight refuses a
    staging boot with it off (`settings.py:215, 229-233`, `preflight.py:118`). It governs
    code delivery, not live controls.
12. **RL readiness stays false**; thresholds are null (`live_defense/readiness.py`,
    `live_defense/serving.py:65-77`).

## Gaps, ranked by what blocks 24/7 operation

| # | Gap | Kind |
|---|---|---|
| 1 | No telemetry collector. Nothing measures a running app and posts windows. Without it every later stage is idle | Partly fixed here: `monitoring/monitoring/collector.py` is an ASGI middleware that sends route-template counters only. Still missing: non-Python apps, per-principal ownership counters (without them the RL policy abstains), and installing it on a real app |
| 2 | No way to reach a customer system. Channel is loopback, environment excludes production | Owner decided to allow it (ADR-0027). Done here: production environment, https control endpoint at a public address, DNS-pinned adapter, self-reported verification, and `monitoring/monitoring/controls.py` as the endpoint an app installs. Each control still needs an owner grant and click |
| 3 | No approved RL policy. v6 is a pinned compatibility fixture; the retrained candidate was rejected by its own gate (`rl-defense/LIVE_RL_GAP_AUDIT.md`) | Closed by the spec for now: thresholds stay unset until the RL owner sets them (`LIVE_DEFENSE_RL_EVALUATION_PLAN.md`: "Thresholds are unset pending RL-owner approval"; `readiness.py` never invents them). The RL policy only recommends either way (docs/01 §4) |
| 4 | v6 is hardwired to the payments-lite topology (`live_defense/policy.py:32-38, 235-248`). On any other app its recommendation is not meaningful | Contained here: v6 now abstains (`skipped_schema`) when any route is outside that topology. A policy for other apps still needs per-application topology and retraining |
| 5 | Nothing connects a decision to an action without a human | Won't do, per the spec: "any change to a real system require[s] a human" (docs/01 §6.3). AUTO-EXECUTE stays rejected |
| 6 | The safe control set is too weak to contain an attack. The candidate policy missed the availability floor because node-level isolate was the only containment | Won't do, per the spec: isolation, commands, database changes, credential rotation, deployment and disabling an app "have no code path" (LIVE_AUTONOMOUS_DEFENSE_PLAN §4.2). The allowed set is rate limit, one-address block, logging, escalate |
| 7 | Shadow inference never ran in production (missing checkpoint in the image) | Bug. Fixed here |
| 8 | Rollback before execution did not stop the control; rollback during verification left it `failed` and blocked all further controls | Bug. Fixed here |
| 9 | No retention for `live_policy_decisions`, first-responder decisions or `live_controls` (`maintenance.py` covers `runtime_windows` and `monitoring_events` only). At one window a minute per app these grow without bound | **Owner decision**: these rows are audit evidence |
| 10 | Rollback jobs dedupe forever on the control id (`live_defense/controls.py:290-297`), so a rollback can be requested once | Moot after fix 8: every rollback job now ends the control in a terminal state. Not changed |
| 11 | Expiry is skipped when the control is not yet `verified` (`live_defense/controls.py:631`). The fixture expires it by itself, but the record never closes | Bug. Fixed here |
| 12 | `control_channels.hmac_secret` is stored in plaintext (documented residual risk) | Fixed here: Fernet-encrypted at rest when `CONTROL_SECRET_KEY` is set (preflight warns when unset). Setting the key on Railway is yours |
| 13 | `test_rl_integration.py` skips in the default environment, so CI does not exercise v6 inference | Test gap |
| 14 | API and twelve workers share one Railway service; a restart pauses detection. No alert when ingest stops for a project | Partly fixed here: the hourly maintenance cycle reports once when an app's telemetry stops for 30 minutes (log, and the ops alert webhook when set). Single-service restarts still pause detection |

## Decisions only the owner can make

Each of these lets Ari change a running system, or changes what counts as proof.

- **Production targets.** Allow a non-loopback control channel and a production
  environment. This is the single switch between a lab and a product.
- **Autonomy.** Whether any control may run without a human click, for which kinds, and
  with what blast-radius limits.
- **Stronger controls.** Whether to allow principal blocks or isolation, which the
  current gate hard-denies.
- **RL promotion bar.** The numeric thresholds a policy must meet before it is served,
  and whether a policy that loses to tuned rules should be served at all.
- **Telemetry scope.** What a collector may read from a customer's runtime.
- **Evidence retention.** How long shadow decisions and control records are kept.

## Fixed in this PR

- `backend/Dockerfile` copies the pinned v6 checkpoint and its manifest, so shadow
  inference can run in production. Output is still a `NOT_EXECUTED` shadow decision.
- `live_defense/controls.py` `rollback_job`: a rollback that arrives before execute now
  rejects the control so it is never applied; a rollback during execute or verify now
  ends `rolled_back` and does not leave an unresolved control.

- `monitoring/monitoring/collector.py`: telemetry collector (gap 1). It sends counts per
  route template and never a raw path, query, header, body or client address.
- `live_defense/policy.py`: v6 abstains on routes outside its trained topology (gap 4).
- `live_defense/controls.py` `expire_job`: a control still executing or verifying at
  expiry is removed and closed instead of skipped (gap 11).

Gaps 2, 3, 5 and 6 are untouched. Each one lets Ari change a running system or lowers
the bar for doing so, and each needs an explicit owner decision.

Not checked: the production Railway environment variables, any live project data, and a
real image build. The Dockerfile change is asserted by a static test only.
