# Action-capability and collateral-damage matrix

Read against `envs/defense_sim.py:{decode_action,_apply_action,_resolve_delayed_effects}`,
`layouts.py:live_decode_action`, `live/loop.py:{_apply_action,_tick_timers,_principal_facts}`,
`live/gateway.py:DefensiveGateway.request`, `live/telemetry.py:build_facts` and
`configs/topology/payments_lite.yaml`. "Enforceable" below refers only to the owned lab.
The product recommendation worker executes **none** of these actions.

| Action / unchanged indices | Simulator behavior | Live lab behavior, duration and specificity | Context, damage and observable effect | Phase1 research availability |
|---|---|---|---|---|
| noop0 | Advance adversary/timers/signals | Advance traffic/timers; existing controls persist | Always available; noop does not cancel a previous block; no new intervention cost | Yes |
| raise_monitoring1+4i | Increase detection level; temporary sensing gain | Same node monitoring raises anomaly sensitivity; default5windows | Node context, ceiling; no direct HTTP denial or containment; telemetry changes | api/payments only, within base mask |
| rate_limit2+4i | Reduce abstract adversary progression; hidden-stage disruption proxy | Drop2/3 of requests per active node (counter persists); default3windows | Any principal incl legitimate/delegated; requests get429; no token/tenant specificity; no traffic means no effect | api/payments only, within base mask |
| isolate3+4i (`isolate_node` is a conceptual name, not actual enum) | Stop progression/spread and probabilistically evict stages before impact | Deny every request mapped to node with503; default3windows; no eviction/patching | Broad blast radius; payments isolation stops all payment traffic, not /me. A db action cannot block an internal DB hop: no db route | api/payments only, within base mask |
| request_reassessment4+4i | After config delay lower finding severity and progression speed | Default4windows, scripted severity reduction to<=.2; no security-agent assessment or patch; does not repair BOLA | Finding>threshold and not pending; observation changes, no actual exploit fix; admin/synthetic effect | Unavailable |
| escalate_to_human21 | Delayed anomaly-targeted probabilistic containment; budgeted | Default3window timer and max3events; no completed human investigation or gateway containment | Cost/budget consumed; pending/budget features change; no demonstrated security outcome | Unavailable |
| block_principal22 (v2+) | Absent | Deny every request by every flagged principal on flagged nodes with403; default3windows | Previous-window detector needs token→principal, object-owner and optional grants; follows token rotation; collateral own/delegated reads blocked too | Base principal availability; cost-aware permits<=2new short actions |
| block_principal_long23 (v3) | Absent | Same targets, default10windows, extends without shortening | Active while eligible target remaining<=short duration; larger residual harm incl quiet windows | Base availability; cost-aware excludes |
| block_top_principal_long24 (v3) | Absent | Long block heaviest flagged principal(s), **all ties**,10windows | Not guaranteed single target; fewer recipients does not mean authorization-aware; legitimate reads by same target still denied | Base availability; cost-aware excludes |

Durations are `LoopConfig` defaults, not seconds. Actions apply **before** traffic and
timers decrement afterward, so the current window counts toward duration. Node indices
0..4 are gateway/api/auth/payments/db. Base masks never add a permission. Research hard
capability exclusions are unavailable actions, never merely a scalar penalty. Residual
controls and valid but unwise choices remain possible. Simulator action effects cannot
be ranked alongside live effects under one metric; no synthetic simulator count costs
are imported as measured live damage.

Existing driver traffic only reaches /payments and /me (payments/api). /auth route
patterns exist but the driver never calls them; bearer validation happens inside the
app, not a separately traversed auth node. Gateway nodes in the abstraction are route
classes, not infrastructure dependencies. A future driver/topology must define a new
capability profile and prove its effects, not reuse this fixed whitelist blindly.

## Proposed narrow control — not implemented

Candidate: a request-level `deny_unauthorized_object_read` rule on selected method/route,
resource/tenant and authorization predicate, preserving own-object reads and explicit
business delegation. This would be deterministic access control, not inferring intent
from a principal's observed own-share. It may make the synthetic BOLA trivially fixable;
compare a real authorization patch as a reference before claiming an RL contribution.

Prerequisites: reviewed authoritative token identity and object-owner lookup, versioned
method/route-specific grant policy, request-level authorization decision/reason, unknown
identity/owner handling, full negative/positive/delegation regression tests in independent
Verify, consistency with application authorization, scope approval, bounded duration and
rollback. Labels cannot come from LLM findings or traffic intent alone. Define denied
unauthorized vs denied-authorized counts separately. Do not install it from a policy.
A new versioned layout/adapter and contract-owner review would be required if represented
as an action; preserve all historical indices and checkpoint interpretation. No new
endpoint, gateway control, shared enum or action index is added in Phase1.
