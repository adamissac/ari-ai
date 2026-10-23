# Deterministic payment-read feasibility

RL-CMDP-002: owner authorized an isolated deterministic feasibility comparison after
Phase 1 merged in PR #388. The owner explicitly selected **zero successful
unauthorized reads and zero denials of valid owner/delegated reads**, per scenario.
Unknown or contradictory permissions abstain and are reported separately.

The committed [protocol](PROTOCOL.json) fixes 18 authored cases, three fixed policies
and 54 in-process HTTP requests. The source/protocol must be committed before the
comparison. No retries, replacement cases, interim tuning, training, historical
scenario replay or customer traffic. Compute limit: 60 seconds. Output is a new
directory and contains all responses, source/protocol pins and runtime packages;
exceptions retain partial rows in FAILURE.json. No learned policy or action registry
is modified. This is a research fixture, not an application authorization deployment.

The exact-resource guard is stateless. It checks trusted fixture ownership and
explicit resource grants at each read. Validity is half-open; revoked/expired grants
cannot authorize. Missing, stale or contradictory context abstains without forwarding.
A blanket-deny baseline illustrates collateral denial; an unguarded vulnerable fixture
illustrates unauthorized access. No traffic-generator labels enter the guard.

These are authored functional cases with known expected semantics, not a randomly
sampled or blinded benchmark. Passing all cases proves only these finite cases;
there is no population confidence interval, production-safety claim or automatic
permission for an RL experiment. Unit fixtures were used during development before
protocol freeze; no numerical budgets were selected from comparison results.

This work does not import or duplicate the operational grant/control lifecycle in
parallel PR #393. It does not register a gateway hook or new shared contract. A later
integration must use canonical contracts and independently verify the trust/freshness
of ownership and grant inputs; request-supplied context is not an authority.

## Execute once from the committed source

```sh
export PYTHONPATH="$PWD/rl-defense:$PWD/shared:$PWD/standards"
python -m rl_defense.research.feasibility --output /tmp/rl-read-feasibility-001 --protocol-sha256 <committed-protocol-sha256>
```

No timeout control is applied to production. Intervention budget I is not applicable
to this stateless fixture; it has no RL action or expiring principal block. Unknown
cases must all remain unforwarded, independently of the two numerical owner limits.
A fixture pass alone cannot reverse Phase 1's no-go: telemetry/state coverage,
independent integration and future evaluation criteria still need review.

## Executed outcome

The single preregistered comparison completed all 54 requests. Exact-resource guard:
zero unauthorized successes, zero owner/delegated denials, all six unknown cases
unforwarded. Unguarded access failed seven unauthorized cases; blanket denial failed
five legitimate cases. [Retained evidence](../../../rl-defense/results/deterministic-feasibility-001/README.md).

Next: independently specify and verify extraction/freshness of actual application
ownership and grant context, revocation races and request binding. The current
synthetic single-resource fixture cannot establish those properties. No-go for new
RL training remains; prefer a deterministic application repair if sufficient.
