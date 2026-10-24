# Authorization context provider proposal, version 0.1.0

Status: implemented behind the owned research fixture only; proposed for future
cross-system adoption. No external integration, shared API, RL observation change,
new training, policy promotion or operational control is introduced.

The customer application or its trusted authorization service must remain the
canonical producer of resource-read permissions. For this research environment,
payments-lite's private Store supplies token bindings, customers and payment owners;
the existing operator-managed lab ReadGrant tuple supplies delegation. The base
payments-lite Store has no delegation table. Ari does not infer permission from
findings, model output, traffic-generator labels or ControlGrant execution records.

## Minimal interface and compatibility

`AuthorizationContextProvider.capture(credential, resource, tick)` returns an
immutable `AuthorizationSnapshot`. The only implementation is
`PaymentsLiteAuthorizationProvider`. Credentials authenticate through trusted token
records; resource identifiers select trusted records. Neither argument asserts an
owner or grants. HTTP headers/query/body claiming ownership or delegation are ignored.
Credentials are never retained in the snapshot.

The internal snapshot contains provider version `0.1.0`, authority identifier,
clock-domain identifier, authority revision and the existing immutable ReadContext.
`classify(tick)` yields exactly `owner`, `delegated`, `unauthorized` or `unknown`.
Only the first two permit forwarding; unknown abstains (503), unauthorized denies
(404). Missing identities/resources/grant knowledge, contradictory records,
clock rollback and stale snapshots are unknown. An empty complete grant set is
known absence; None means unavailable. Grants use exact principal/owner/resource
matching and half-open [valid_from, expires_at) intervals. Revoked, expired and
not-yet-valid grants do not authorize reads.

Time is integer monotonic fixture ticks, **not UTC**. Ticks are comparable only
inside the declared clock domain. Revision increments for every completed trusted
lab mutation. It identifies a fixture state, not a database transaction or external
revocation feed. A captured snapshot does not learn subsequent mutations. The lab
serializes capture, downstream processing, release and trusted updates under one
lock, rechecks expiry before release, and owns all writers. A snapshot alone is
not a reusable permission credential. External/multi-worker adapters would require
transactional or equivalent consistent capture and release-time invalidation;
those are requirements, not implemented capabilities.

The proposal reuses ReadContext/ReadGrant and the deterministic authorization kernel;
it does not publish parallel shared network models. Before a second subsystem or
external provider consumes it, agree the canonical shared contract in shared/,
including trusted principal authentication, application/tenant binding, provenance,
clock conversion, freshness bounds, revision consistency and failure semantics,
then generate JSON Schema/TypeScript and consumer contract tests. Unsupported
versions must fail closed; incompatible semantics require a new version. No
ControlGrant, AuthorizedScope or model score can substitute for read permission.

## Future RL observation: causal, bounded and separately versioned

No provider fields enter any existing policy observation in this implementation.
A future observation layout must receive only facts actually available to the
controller before its action. For example: the completed previous window's observed
requests, each paired with context captured by the trusted provider when processed,
can produce owner/delegated/unauthorized/unknown counts, coverage and context-age
features. Unknown must retain a separate coverage mask; it must not become an
unauthorized label or zero-cost success. Opaque principals, resource IDs, credentials
and raw grants need not enter the policy vector.

At decision t: finish observable window t-1, freeze its available context and cutoff,
build observation t, then choose action t. Traffic/outcomes during window t become
eligible only for the next observation. Record event occurrence and knowledge-arrival
times separately; both must be at or before the cutoff. A late-arriving fact belongs
to a later observation. Never backfill an old observation with a later ownership
transfer, revocation, corrected record or successful attack result. Capture the
clock domain, revision, expiry and feature-layout version alongside each observation
for replay. Missing/stale or inconsistent context stays unknown. A provider snapshot
for one request cannot label requests it did not observe.

Exclude generator attack/legitimate labels, future scenario schedules, future grant
changes, hidden owner tables for unseen requests, future-window requests and action
rewards/outcomes. Permission knowledge is permissible only if the real deployment
could obtain the same trusted information at that moment; offline oracle access is
not evidence of deployable observation availability. Keep evaluation truth separate
from policy inputs and test prefix invariance: changing future traffic/permissions
must not change any earlier observation. Compare missing/late-provider behavior and
record capture latency before claiming feasibility. These gates remain proposed;
no new population experiment or readiness claim follows from adapter unit tests.

The deterministic read-permission gate remains independent of any learned policy.
A policy recommendation cannot override unknown context or authorize a read, and
read permission cannot authorize Ari to execute an infrastructure control.
