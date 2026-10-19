# ADR-0014: Seven-agent adversarial post-training is decoupled, offline, and gated

| Field | Value |
|---|---|
| Status | Proposed |
| Date | 2026-10-19 |
| Deciders | UNASSIGNED (ratify with RL + security-agents owners) |
| Related | [architecture/seven-agent-rl-adversarial-integration](../architecture/seven-agent-rl-adversarial-integration.md), [ADR-0008](0008-offline-double-dqn.md), [ADR-0006](0006-docker-sandbox-no-network-default.md), [09](../09_RL_DEFENSE_SYSTEM.md), [17](../17_RL_EVALUATION_PROTOCOL.md), [15](../15_SECURITY_BOUNDARIES.md), RQ-005 |

## Context
A future phase would let the seven-agent offensive pipeline (Scout→Probe→Trace) generate
scenarios that the RL defender trains against, forming an adversarial learning loop. The forces:
hackathon time; the RL system is currently offline-simulator-only (no live telemetry, no action
execution); safety rules require deterministic authorization and no autonomous action on real
systems; and the agents' textual output is explicitly non-authoritative. We must *account for*
this integration in the architecture without coupling or prematurely building it.

## Decision
1. **Decouple.** The orchestrator never imports the RL package and never triggers training. The
   two systems exchange only persisted, versioned typed artifacts (`OffensiveScenario`,
   `EpisodeSpec`, `ExperienceDataset`, `PromotionReport` — proposed for `shared/`).
2. **Instrumented ground truth only.** A scenario enters training/eval only when attack success is
   defined by sandbox instrumentation or a verified attack path, never by any LLM text field.
3. **Offline and candidate-only.** Retraining is offline and produces a *candidate* checkpoint;
   promotion to the deployed policy is a separate, human-gated, reversible step. No auto-update
   during incidents; no online learning on live signals.
4. **Reproducible splits.** Each scenario is assigned to exactly one of train/val/holdout by id
   hash; never train and evaluate on the same scenario.
5. **Defer.** No implementation until the standalone live RL Defense Lab is functional, measurable,
   and tested. Until then the design doc is the deliverable.

## Options considered
| Option | Pros | Cons |
|---|---|---|
| Decoupled artifact hand-off, offline, gated (chosen) | Safe; preserves ADR-0008/0015 boundaries; testable; reversible | More moving parts; lossy projection onto the 5-node sim |
| Orchestrator calls training directly | Fewer artifacts | Couples pillars; risks online/live-model changes; violates ADR-0008 |
| Treat each agent as an independent attacker / each finding as an episode | Simple mental model | False: agents are a pipeline; most findings aren't reproducible episodes; uses LLM text as truth |
| Build now, alongside the standalone RL lab | "Done sooner" | Prerequisite (live RL pipeline) unmet; premature coupling |

## Consequences
- Claims stay bounded to the simulator (RQ-005); the projection from real findings to the 5-node
  abstraction is lossy and must be documented per scenario.
- Adds a contract-first dependency on `shared/` for the new schemas before any code is written.
- Makes the adversarial loop asynchronous and versioned by construction, not a live feedback loop.

## Revisit when
The standalone RL Defense Lab has a working live telemetry → inference → action → reward → training
pipeline (the implementation gate), or the simulator is validated against real telemetry (RQ-005).
