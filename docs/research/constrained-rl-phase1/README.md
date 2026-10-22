# Ari AI constrained RL — Phase 1

**Phase1 foundation implemented; Phase2 stopped. No-go now for a new constrained-DDQN
or discrete-CQL prototype.** Conditional next architecture: cost-aware DDQN only after
feasible controls, state/data support and independently specified budgets are established.
No training study, promotion, deployment or production recommendation change occurred.

- [Architecture audit: exact modules, functions and tests](AUDIT.md)
- [CMDP specification: separated measured objectives and constraints](CMDP.md)
- [Action-capability / collateral-damage matrix and narrow-control prerequisites](ACTIONS.md)
- [Offline dataset readiness and missing information](DATASET_READINESS.md)
- [Architecture comparison, four papers and precise no-go gate](DECISION.md)
- [Executed tests and review corrections](VERIFICATION.md)
- [Fixed baseline execution plan](PLAN.md)
- [Baseline results and reproducibility](../../../rl-defense/results/constrained-phase1/README.md)
- [ADR0019 proposal and explicit earlier-ADR conflict](../../decisions/0019-constrained-rl-foundation.md)

The new isolated `rl_defense.research` adapter uses canonical EvidenceRef without a
new shared/public API. It separates negative compromised-read reward and measured
legitimate-denial cost, retains old reward, validates unknowns, reads compatible pinned
old logs, and evaluates fixed lab baselines with complete request evidence and clustered
bootstrap intervals. Hard capability constraints are masks; expected damage is a
separate statistical question. No model can authorize real action or turn agent prose
into a verified reward.

Executed140baseline episodes /4,200windows. The two-short-intervention heuristic had
99.50% benign availability but93.16% attack compromise; it is not a successful defense.
Adapted8,400old training transitions read-only: aggregate costs known;280initial masks,
all propensities and all delegated-denial attributions unknown. Familiar training seeds,
shielded selection semantics and partial observation prevent broader effectiveness claims.
Test commands/results and evidence limitations are recorded with the results/handoff.

Proposed next readiness work: [NEXT_GATE.md](NEXT_GATE.md), without execution
authorization or invented safety thresholds.

Supported historical readiness command: `python -m rl_defense.research.legacy`.
The result-directory reader is frozen archival source, not the supported verifier.
