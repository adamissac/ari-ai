# Feasibility of existing and candidate actions

Existing indices/weights/semantics stay unchanged. `layouts.py` and
`live/actions.py` remain the canonical old layout definitions.

- Noop (old 0): real absence of adaptive intervention; always available.
- Node rate_limit (1+4i): real gateway 429s on api/payments; drops authorized and
  unauthorized requests indiscriminately. Other nodes lack driven route effects.
  It is not request-scoped authorization-aware throttling or measured load relief.
- raise_monitoring (2+4i): changes detector sensitivity, not gateway containment.
  No validated value-of-information objective; exclude from candidate training.
- isolate (3+4i): broad 503s on driven api/payments routes; no actual infrastructure
  isolation/attacker eviction. Cannot satisfy strict preservation of legitimate reads.
- request_reassessment (4+4i): timer/scripted severity change, no executed fix;
  unsupported as security reward or production assessment completion.
- escalate_to_human (21): timer/budget only in the HTTP lab; no actual resolved human
  case. Unsupported rather than rewarded for creating a label.
- principal block (22), long (23), top-long including all ties (24): real denied
  requests follow token-to-principal identity and timers, including own/delegated
  reads. Broad principal blocking is not added to the candidate set.

Candidate action schema `adaptive-actions/0.1`, independent from old indices:

- 0 noop: supported, no control target required.
- 1 diagnostic_logging: unsupported; needs bounded capture/overhead plus a measured
  improvement in later diagnosis, with privacy and storage limits.
- 2 human_investigation: unsupported; needs authenticated submission/completion,
  delay, resolution truth and measured labor/budget units.
- 3 scoped_rate_limit: unsupported; needs a validated target, deterministic gate,
  trusted context and measured residual load/availability benefit without legitimate
  denial. Existing node sampler is not this control.
- 4 source_containment: unsupported; no trusted source identity distinct from shared
  credentials/NAT, narrow adapter or independent efficacy/collateral evidence exists.

Executable candidate mask is exactly [true,false,false,false,false]. Invalid,
unsupported, boolean and out-of-range choices raise ValueError independently of
policy. There are no duration/budget arguments that can enable unsupported actions.
No-op's lack of an operational execution does not mean all future cost budgets are
zero. Proposed persistent actions need a full ledger: target, issue/expiry tick,
release/revoke record, cooldown and remaining independently approved budget. Current
adapter leaves those feature values unknown. Permission, expiry, scope or budget
failure must reject before execution; future reset/termination must tear down controls
and preserve ledger evidence. None of those adapters is implemented in this phase.

A policy cannot change ownership, issue grants, modify the deterministic guard, or
use read permission as an Ari ControlGrant. Future experiments must count proposed,
rejected and applied actions separately and freeze masks before every choice.
