# ADR-0017: Runtime principal detection feeds the RL defense (pseudonymous, aggregated)

- Status: Accepted
- Date: 2026-10-19
- Decision: Alan (interim `shared/` approver) asked for this in the session that made the
  change; contracts 0.14.

## Context

The promoted v6 live policy (`rl-defense/results/live-retrain-v6/`) defends by blocking
the principals the gateway's detector flags for cross-tenant reads. In the product the
backend built `PlatformFacts` from findings and per-route error heuristics only. It had no
principal detector, so a live policy served there could never recommend a block, and its
node signals came from a different detector than the one it was trained with. A
successful BOLA read returns 200 and trips no error heuristic.

## Decision

1. **Detection happens at the operator's own instrumentation** (gateway or sidecar): who
   the bearer token belongs to versus who owns the requested object, with the business's
   delegation grants applied. This is the lab gateway's detector. The platform never sees
   requests, tokens, payloads or raw identities.
2. **The reporter sends aggregated, pseudonymous counters** with its runtime route windows:
   `RouteWindow.principals: [PrincipalCounts]` with `cross_tenant` / `delegated` / `own`
   per principal. `PrincipalRef` must match `^prn_[A-Za-z0-9_-]{4,64}$`, which rejects
   emails and raw ids. The reporter derives it with an HMAC under a key the platform never
   sees (reference: `rl_defense.live.report`). Counts are validated against the route's
   requests.
3. **No schema migration.** Counters are stored with the route window (existing JSONB).
   Drill windows are excluded from RL input, as for route signals.
4. **The RL mapping uses the lab's detector definitions** (`platform_mapping`):
   - the live v3 principal fields;
   - node `alert_rate` / `anomaly_score` at least the lab's detection signal (cross-tenant
     attempts plus errors), combined by max with the existing heuristics.

   A test proves that, for the same window of real requests, the platform's fields and
   node signals equal the lab loop's.
5. **Recommendations name whom a block would cover**
   (`DefenseRecommendation.principal_targets`, pseudonymous). The operator maps the
   pseudonyms back. Nothing is executed; ADR-0008's recommendation-only path is unchanged.
   The platform enforces no block, so the block-state features stay 0.

## Consequences

- With a reporter that detects principals and a validated BOLA finding on record, the v6
  policy served by the worker recommends `block_principal` targeting exactly the flagged
  principal (`backend/tests/test_rl_integration.py`).
- **Known training-distribution gap:** v6 was trained with fixed baseline finding
  severities on every node. The product supplies real finding severities, which are 0 on
  clean nodes. With lab severities substituted, platform and lab recommendations agree on
  30 of 30 checked train windows. With real severities, in windows where nothing is
  flagged, v6 tends to recommend `escalate_to_human` instead of `noop`. Training with
  finding-derived severities closes this. It is a follow-up and was not patched by faking
  severities.
  **Update (v7, 2026-10-20):** `rl-defense/results/live-retrain-v7/` trained the v6 method
  with per-episode, platform-producible severities. On train windows with real
  severities, the v7 candidate recommends `noop` in every quiet window and
  `block_principal` in every flagged one, and lab and platform agree on 200/200 windows.
  The pre-registered gate rejected it on one per-scenario check (`quiet_week`), and its
  held-out return ties v6. **v6 stays the promoted policy, so the gap stays open in the
  product** until a candidate trained this way passes the gate.
  **Update (v8, 2026-10-20):** `rl-defense/results/live-retrain-v8/` retrained the v7
  method on a train mix with low-intensity, mostly quiet traffic. Its candidate keeps the
  fixed behaviour (`noop` in 178/178 quiet train_v8 windows, `block_principal` in 102/102
  flagged, lab/platform 280/280), and its historical gate returns `recommend_promote` on a fresh
  holdout_v8 against a newly trained simulator baseline, not incumbent v6. It ties v6 on held-out return and is worse than v7 there, and the
  pre-registered hypothesis (better on low-intensity traffic) is not supported. **The gap stays open in the product.** The historical report cannot authorize
  replacement of v6; incumbent-bound checks reject the comparison. Nothing was promoted.
  **Update (v9, 2026-10-21):** Five fixed training seeds evaluated against actual v6 on
  fresh holdout_v9 all reject. Overall return gain is −0.0458 (95% training-seed CI
  −0.1758 to +0.0843); mixed rotation regresses despite improved compromise fraction.
  See `rl-defense/results/live-retrain-v9/PROVENANCE.md`. v6 remains deployed.
- Window-size shift: the lab's features are per lab window (about 20 requests). A
  reporter's windows can be larger. The features are ratios or capped counts, but volume
  normalization (`flagged_volume`, /6 per principal) assumes lab-sized windows.
- Reporters without principal detection are unaffected: no counters, so the defaults
  apply, and every earlier payload validates unchanged.
