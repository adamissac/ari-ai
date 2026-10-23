# Candidate objective, separate outcome channels

Proposed objective: maximize attributable measured security benefit subject to
separate cumulative cost constraints over an approved episode horizon. Every term
needs its own units, denominator, evidence and missing reason. No numerical training
budgets or weighting defaults are approved by implementation of this proposal.

R: incremental adaptive benefit relative to the deterministic authorization baseline,
only where measured. Under the current guarded read task this is not demonstrated;
`adaptive_security_reward` remains null. Never award the adaptive policy credit for
an application authorization denial. Non-200 is not proof of prevention. Unknown
context abstention is a safety behavior, not a positive reward that can be farmed.
No bonus for an investigation until a defined independently verified resolution and
latency exist. Paired outcome differences, if later justified, estimate a policy
contrast, not which individual unseen counterfactual request was prevented.

Separate C channels:

- Owner adaptive-denial count: trusted owner reads actually refused by an adaptive
  control. Owner completions require valid response identity, not HTTP 200 alone.
- Delegate adaptive-denial count: same for exact current valid delegation.
- Other legitimate disruption: unknown until trusted instrumentation defines it;
  no assumption that everything not labelled attack is production legitimate truth.
- Unnecessary control duration: needs a retained control ledger and a precommitted
  definition of unnecessary; no hindsight-labelled benefit or arbitrary timer score.
- Operational cost: measured adapter resource units/human work only when captured;
  intervention count can be retained as a separate count, never called dollars.
- Unknown-context outcomes: report separately with coverage. Do not relabel unknown
  as unauthorized, valid denial, cost zero or attack prevention.

The pure adapter reports descriptive known owner/delegated adaptive denials among
observed records; incomplete telemetry cannot certify a population cost. Operational
and duration costs stay null. Historical negative-compromise reward, aggregate benign
cost and original scalar reward keep their original meaning and artifacts; synthetic
simulator disruption is not measured HTTP collateral damage.

The owner's prior feasibility limits remain zero successful unauthorized reads and
zero valid owner/delegated denials per scenario, with unknown separately reported.
These do not set new latency, duration, effort, intervention or statistical budgets.
All such future thresholds remain UNSET pending independent owner approval. A hard
read-permission gate and budget check cannot be replaced with expected reward penalties.
