# Fixed baseline comparison design, not executed

All eligible comparators must share the trusted guard, provider clock/freshness,
request distribution, action capabilities, budgets, horizon and measurement semantics.
Use the same fixed exogenous episode seeds for paired contrasts, but resample whole
independent episode/seed clusters. Pairing is not independent replication.

1. **No adaptive intervention + trusted authorization**: primary strong reference.
   It does not deserve an RL label. Compare any candidate incrementally to it.
2. **Existing rules**: retain the historical threshold rule definition and pins for
   historical reports. On a new residual task, use only independently feasible
   actions and call a restricted version a different policy. Existing broad blocks
   cannot be granted to only one arm or silently rewritten as scoped controls.
3. **Authorization-aware deterministic policy**: exact resource guard plus noop for
   the present fixture. This dominates using noisy intent estimates for permissions.
   A future policy may act only on validated residual measurements.
4. **Narrow threshold policy**: proposed fixed threshold and cooldown on an approved
   residual signal (e.g. measured service load). Threshold, duration and budget are
   UNSET; cannot evaluate until sensor/control efficacy and owner values exist.
5. **Frozen v6**: old 55/25 layout and checkpoint bytes are incompatible with candidate
   69-channel/5-slot diagnostic schema. Do not pad/reorder, retrain, map actions or
   reinterpret weights. A legacy-side diagnostic comparison must retain its old
   observation/action semantics and be explicitly non-comparable for new-task claims.

With the currently executable candidate mask, every feasible deterministic policy
reduces to noop. This is absence of a demonstrated performance gap, not evidence
that RL has failed or that a new threshold baseline has been evaluated. No baseline
population evaluation is run in this phase; historical fixture counts are not fresh.
