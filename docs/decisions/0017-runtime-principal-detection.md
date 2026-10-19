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
- Window-size shift: the lab's features are per lab window (about 20 requests). A
  reporter's windows can be larger. The features are ratios or capped counts, but volume
  normalization (`flagged_volume`, /6 per principal) assumes lab-sized windows.
- Reporters without principal detection are unaffected: no counters, so the defaults
  apply, and every earlier payload validates unchanged.
