# Live Defense Phase 3 — pilot evaluation

Status: **observed on `feat/live-defense-phase3-shadow-runtime`**. This is a
shadow-runtime evaluation. It is **not** evidence that shadow recommendations
reduced real compromise. There is no comparison arm against an unprotected
production system, and this slice never executes a network control.

Branch head at evaluation time: see git log on this file's commit.
Base: `origin/main` `6e98b23` (Phase 2 PR #391).
PR: https://github.com/adamissac/ari-ai/pull/392

## What was exercised

Owned `examples/payments-lite` counters posted as `source=owned_staging` with an
application-bound ingest token → existing `/ingest/runtime/{project_id}` →
`live_defense_shadow` job → deterministic rules (and frozen v6 only if serving
assumptions hold) → persisted `LivePolicyDecision` (`enforcement: NOT_EXECUTED`)
→ Live Defense dashboard (Overview, Investigation, Explainability) → analyst
accept/reject. Accept does not enqueue adapters and is not written as an RL label.

## Observed metrics

| Metric | Sample | Result | Notes |
|---|---|---|---|
| Ground-truth windows (`examples/payments-lite/live_defense_shadow/ground_truth.json`) | n=3 (benign, repeated auth failures, reporter-classified cross-tenant) | All three produced a persisted shadow decision; all `executed=false`, `enforcement=NOT_EXECUTED`, `simulated=false` | `backend/tests/test_live_defense_phase3.py::test_payments_lite_ground_truth_replay` |
| HTTP 200 without principals classified as IDOR | n=1 benign window + dedicated unit tests | Not classified as IDOR; `authorization_context=unverified`; ownership-unknown is not a finding | `monitoring/tests/test_detect.py`, `test_http_200_is_not_idor_and_v6_does_not_silently_decide` |
| Cross-tenant rule requires reporter `principals` | n=1 window with `prn_*` counts | `cross_tenant_with_ownership` fired; still NOT EXECUTED | Ground-truth + `test_cross_tenant_rule_persists_without_execution` |
| Duplicate window | n=2 identical POSTs | One stored decision | `test_duplicate_window_persists_one_shadow_decision` |
| Replay source labelled live | n=1 `source=replay` batch | Events `simulated=true`; no `LivePolicyDecision` | `test_replay_source_is_labelled_simulated_and_skips_shadow` |
| Secret-like payload stored | n=1 batch with `Bearer …` | HTTP 422; quarantine event without the secret | `test_secret_like_payload_is_quarantined_and_not_stored` |
| Analyst accept executes a control | n=2 reviews (accept + reject) on a real decision | `executes=false`, `enforcement=none`; job count unchanged | `test_analyst_accept_on_live_decision_does_not_execute_or_label` |
| Tenant isolation | outsider org | 404 on list/get/review | Phase 3 API tests |
| Browser-callable apply/isolate/rate-limit/block | FastAPI route table | No such POST paths | `test_no_browser_callable_enforcement_routes` |
| Frozen v6 inference in this developer venv | n=windows that would otherwise be eligible | `inference_status=skipped_unavailable`; `top_actions`/`q_margin`/`observation` null | `rl_defense` + torch are not installed in the default workspace; Q-values were **not** synthesized |
| End-to-end authenticated UI | 1 Playwright run against real API+Postgres+worker+`next start` | 1 passed (6.6s) | `frontend/tests/e2e/live-defense.spec.ts` |

### Test commands (executed)

```
make check
  ruff pass; format 165 files; shared.export --check 124 files; examples check pass

uv run mypy
  Success: no issues found in 40 source files

uv run pytest -q backend/tests monitoring/tests/test_detect.py shared/tests/test_contracts.py
  239 passed, 8 skipped in 123.81s
  skips: rl_defense missing (4), Docker sandbox opt-in (2), live LLM (1), TSC unset (1)

npm run lint --prefix frontend && npm run typecheck --prefix frontend
  pass

npm test --prefix frontend
  325 passed / 77 files

npm test --prefix frontend/transport
  35 passed

npm run build --prefix frontend
  pass

cd frontend && ../.venv/bin/python tests/e2e/stack.py tests/e2e/live-defense.spec.ts
  1 passed (7.5s) — Chromium, real stack, provider_mode=fake for unrelated LLM paths

gitleaks git --log-opts='origin/main..HEAD'
  3 commits scanned, no leaks found
```

`git diff origin/main...HEAD -- rl-defense` is empty. No training run, no checkpoint
write, no promotion.

## Unavailable / not measured

| Claim | Why unavailable |
|---|---|
| Shadow recs reduced real compromise | No production traffic, no untreated control group, no executed control |
| Frozen v6 live precision/recall on this host | Inference skipped (`skipped_unavailable`) without torch/`rl_defense`. CI `rl-integration` is the job that can load the hash-pinned v6 file. Quiet windows still abstain (ADR-0017) even when v6 loads |
| Time-to-detect on a customer staging fleet | Only the three fixture windows plus e2e ingest spikes |
| False-positive rate in production | Not observed |
| Health of the worker as a liveness verdict | `DefenseHealth.status` is always `unknown`; HTTP 200 is not treated as healthy |
| Autonomous containment | Not implemented (Phase 4) |

## Limitations

1. Telemetry is aggregated route counters from an owned reporter, not packet capture
   or third-party WAF events.
2. Cross-tenant findings require the reporter's ownership classification. HTTP 200
   alone is never treated as IDOR.
3. v6 was trained with fixed finding severities. Quiet windows with real severity 0
   must not silently use v6 as a live decision-maker; this code abstains.
4. The e2e incident that also links a simulation-derived `DefenseRecommendation`
   is labelled synthetic because of that recommendation. Incidents opened from
   **only** authenticated `owned_staging` events are not labelled replay
   (`test_incident_from_owned_staging_events_is_not_labelled_replay`).
5. `/live-defense-pilot` remains sample layout and is never mixed with live records.

## Customer-pilot blockers

- A hosted API worker with `rl_defense` + CPU torch if the customer wants v6 Q-values
  on eligible (non-quiet, ownership-verified) windows. Rules and abstention already
  persist without that.
- An owner-registered sandbox/`owned_test` app that actually emits `owned_staging`
  counters (the payments-lite fixture is the reproducible stand-in).
- No production environment grant exists, by design.
- Analyst staffing: accept is an opinion, not a two-person incident approval.

## Recommended Phase 4 scope (do not implement here)

1. Independent `authorize.check` over owner grants, allowlist, blast radius, budget,
   expiry — still no model-widened permissions.
2. Idempotent adapters only for explicitly granted kinds (rate-limit / isolate /
   block-source) talking solely to the owner-registered control URL.
3. A live-defense incident machine (DETECTED → … → EXECUTING → VERIFYING) separate
   from NIST human lifecycle, with two-person gates before EXECUTING.
4. Verification from new telemetry and automatic expiry/rollback.
5. Honest eval with a comparison design before any “reduced compromise” claim.

Until those exist, Ari records a shadow recommendation and does not take automatic
control of customer traffic.

## Screenshots (authenticated pages, not sample layout)

Copied to `/cursor/stores/self/media/live-defense-phase3/`:

- `staging_apps_token_once.png`
- `overview_authenticated_shadow.png`
- `investigation_nist_incidents.png`
- `incident_linked_evidence.png`
- `explain_shadow_review_not_executed.png`
