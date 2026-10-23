# Current implementation and historical evidence

Inspected merged PR metadata and source on 2026-10-23:

- #388, `09e8cabfa47bbc2324849489e5c4cb58aba0d5af`: measured reward/cost adapter,
  fixed baseline feasibility, source-proof tooling; constrained neural training absent.
- #394, `cb40ca6b75d98f69a3d97e3cfcb544d2d3cb8ab7`: finite authored exact-resource
  guard comparison, not independent population evaluation.
- #396, `7adf509cbef80f21e9c63e341e141879836feb3e`: owned private-Store wrapper,
  request context and serialized trusted mutations.
- #407, `235ef3f20b5234477b87118a46d61fbda2f10fdb`: buffered response schema,
  identity and owner binding; negative and authorized-read regression checks.
- #410, `74a0a3c202fec943e78c8ca03b0c0ba445639c7a`: original finite evidence
  audit, explicitly inconclusive timing/generalization readiness.
- #414, `b2b7d53b46f40535e3cacb330271cb1a6e3f07d4`: internal provider 0.1.0,
  trusted Store plus existing lab-managed grants, four authorization categories.

The actual Double DQN in `agents/ddqn.py` uses online masked argmax, target-network
value, replay batches, Huber TD loss, optimizer gradients and hard/soft target
updates. Epsilon exploration may weight disruptive actions. Optional `cql_alpha`
already adds logsumexp(all actions)-Q(chosen); it is not a new cost-constrained
learner or proof of offline safety. No second implementation is warranted.

`layouts.py`: simulator 48 observations/22 actions, live_v2 49/23, live_v3 55/25.
Live v3 controls expose aggregate/max durations and detector shares, not complete
per-target timers, authority freshness, budget or decision propensities.
`live/loop.py` observes a warm-up window, applies an action, drives the next window,
then records its outcomes and next mask. Invalid live choices become noop, losing
the proposal; the new pure adapter rejects instead. `live/adversary.py` explicitly
keeps traffic paired independently of defender choices. No causal feedback from
containment to adversary adaptation, no queue/service-load model, no measured
completed human investigation, and no diagnostic information-acquisition outcome
has been established. Node reassessment is a scripted severity change, not repair.

`research/payment_read_lab.py` uses trusted identity/owner/grants and response
binding. `authorization_provider.py` classifies captured context; it does not
produce per-window event logs or alter any RL vector. Application authorization
stays independently enforced; a learned policy cannot issue permissions.

Frozen live v6 remains checkpoint SHA256
`8113a37f4ff9360a9efed2e9f499c4b2ae36e97bfb78372436f97da106fc05f1`.
Its complete log and selected prefix overlap; original lineage overcount and skipped
updates remain documented in `results/live-retrain-v6/PROVENANCE.md`. V7–v10,
duration-screen validation and earlier holdouts have been exposed. None are fresh
selection or independent holdout data. The deterministic 18-case/54-request result
has unverified strict response-deadline compliance and missing original Python
identity; later fixes/tests cannot retroactively repair that evidence.

New on main since #414: #418 includes `protocol-v1-retrain` simulator results and
sets Railway worker checkpoint defaults to SHA256
`666145e00d4ee3b9a1839179d9d9aca5a245c20fe7a173e2cb960e34e0393fe8`.
That is a separate simulator checkpoint, not the live v6 champion. Its report uses
already exposed simulator evaluation scenarios/seeds and synthetic disruption;
do not transfer those numbers into the guarded HTTP research task. This assessment
does not change deployment defaults, customer controls, either checkpoint, or any
promotion record. ADR-0019 and proposed ADR-0022 document scope mismatches; no
blanket production-enforcement authority is inferred from them.

The new inventory verifies fixed input hashes and structural consistency, not the
entire execution-source/runtime proof again. Existing historical verifier receipts
retain their own limitations and provenance. No policy or holdout was executed.
