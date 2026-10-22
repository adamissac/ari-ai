# Live Defense Phase 3 plan (3.0)

Status: **implemented** on `feat/live-defense-phase3-shadow-runtime`. This is the
shadow-runtime slice. Phase 4 enforcement is out of scope.

Base: `origin/main` at merge of Phase 2 PR #391 (`6e98b23`). Codex owns RL
research (PR #388, `rl-defense/` training/eval/checkpoints/promotion). This work
does not train, promote, or edit v6 weights.

## What Phase 3 adds

Authenticated owned-staging telemetry → deterministic rules (and frozen v6 only
when serving assumptions hold) → persist a genuine `LivePolicyDecision` with
`enforcement: NOT_EXECUTED` → dashboard shows it → analyst review records an
opinion → **no automatic control of traffic**.

## Order of work

| Step | Scope | Notes |
|---|---|---|
| 3.0 | This plan + contracts 0.17.0 | Additive. `LivePolicyDecision` is a new type because `DefenseRecommendation.simulation_derived` is `Literal[True]`. |
| 3.1 | Authenticated tenant-isolated ingest | Reuse `/ingest/runtime/{project_id}`, `runtime_windows`, ingest tokens, SKIP LOCKED queue. `owned_staging` requires an application-bound token. Validate, dedupe, provenance, quarantine secret-like payloads, existing per-token rate limit. Never live-label replay. |
| 3.2 | Deterministic rules | `monitoring/detect.py`. Findings from reporter counters only. HTTP 200 ≠ IDOR. Missing ownership → unverified, not an authorization finding. |
| 3.3 | Frozen v6 shadow inference | Hash-pinned `rl-defense/results/live-retrain-v6/candidate_online.pt`. Run only when source, completeness, schema, mask, freshness, target action, and authorization context are valid. Quiet windows: **do not** use v6 as a live decision-maker (ADR-0017); rules or explicit abstention. Never execute network controls. |
| 3.4 | `LivePolicyDecision` producer | Persist only if rules or validated inference ran. Q-values null when inference did not run. Cursor pagination + project auth. Shared Pydantic → generated TS. |
| 3.5 | Frontend | Extend Overview, Investigation, Explainability. Poll existing APIs. Unknown correlations stay unknown. Sample layout stays labelled and isolated. |
| 3.6 | Analyst review | Accept does not execute, does not enqueue adapters, does not write RL labels. |
| 3.7 | Owned staging demo | `examples/payments-lite/live_defense_shadow/` — benign + controlled malicious counters, reproducible ground truth, no third-party attacks. |
| 3.8 | Tests | Reliability/security tests, lint, typecheck, frontend+backend, prod build, gitleaks. Honest skips if torch/`rl_defense` is absent. |
| 3.9 | Pilot eval report | Observed vs unavailable metrics, sample sizes, limitations. No claim that shadow recs reduced real compromise. |

## Explicit non-goals (do not begin Phase 4)

- Autonomous enforcement
- Browser-callable apply / isolate / rate-limit / block APIs
- DETECTED → EXECUTING incident machine
- Production environment grants
- Training, dataset, v6 weight, or promotion-registry edits
