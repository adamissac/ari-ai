# Read-only finite-fixture readiness audit

RL-CMDP-005 closes a machine-readable readiness gap. The original result's
`passes_owner_limits` describes numerical authored-case counts, not complete
feasibility, runtime-budget verification, production safety or training approval.

The supported command executes the auditor from a private read-only checkout of
the captured Git commit, using the existing snapshot isolation helper:

```sh
export PYTHONPATH="$PWD/rl-defense:$PWD/shared:$PWD/standards"
python -m rl_defense.research.readiness
```

The local repository must contain the recorded execution commit (a full clone,
or an explicit prior fetch of that commit). RL CI checks out history for this
provenance test; the auditor never fetches missing objects itself.

The audit never imports the collector, creates an application, sends requests,
trains, promotes or changes its input bundle. It reads bounded captured bytes,
requires the fixed original evidence-index digest and result hash, resolves the
actual execution commit object, and retrieves the exact protocol from that commit.
It independently checks all 54 ordered case/policy units, known labels, status and
forwarding consistency, and every reported policy summary. Duplicate keys,
nonfinite JSON, unknown schema/profile and bool/integer substitutions are rejected.

The receipt uses canonical EvidenceRef for the original result. It records the
auditor commit/interpreter separately from original execution identity. The original
interpreter was not recorded and cannot be reconstructed from dependency names.
No retrospective runtime metadata or timing values are invented.

## Meaning of the result

- Artifact integrity and descriptive finite-case counts can be verified.
- Original timing-budget compliance and interpreter identity remain unknown.
- Canonical payment authority, database consistency and population feasibility
  remain unverified. Their receipt fields are null, not zero or passing.
- Overall readiness is explicitly `inconclusive`; `rl_training_ready` and
  `promotion_ready` are false. No program may treat the numerical policy flag as
  authorization to train, register, deploy or execute a control.

The auditor is an offline research utility with no serving integration or new
shared/public contract. It accepts only the retained original fixture profile;
future studies need their own reviewed schema and trust anchors. A copied or
self-rehashed bundle cannot supply its own root of trust.

## Next decision

Before a real application adapter, name the payment-authorization fact producer
and agree how identity, ownership, exact delegation, freshness/revocation and
transaction consistency are authenticated together. The platform's operational
ControlGrant authorizes control execution and is not payment-read authority.
A future contract proposal must extend shared contracts through owner review;
this utility does not invent a payment authority or activate a new data source.

No original comparison is rerun or repaired. A separately authorized/preregistered
bounded comparison with complete timing records would be new evidence, not a
replacement for this retained inconclusive result. The RL no-go remains.
