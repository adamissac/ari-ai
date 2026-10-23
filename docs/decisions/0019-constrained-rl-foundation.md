# ADR-0019: Isolated, measured-cost constrained-RL foundation

- Status: Proposed; Phase1 implementation owner-authorized, future training/design unratified
- Date: 2026-10-22
- Owner: Alan; review requested from Adam (RL)
- Scope: RL-CMDP-001, offline analysis and fixed owned-lab baselines only

## Context and explicit documentation conflict

ADR0008's recommendation-only simulator scope and ADR0014's statement that the live
lab does not exist conflict with the subsequently implemented `rl_defense.live`
owned-payments lab. ADR0017/0018 document portions of that implemented lab and the
recommendation gap, but are not permission for customer containment. This ADR raises
the mismatch rather than treating stale subsystem prose as a production authorization.
Historical experiments and unchanged simulator protocol remain separately identified.

V9/v10 reject despite aggregate return gains; principal-wide control damages legitimate
own/delegated traffic. A new algorithm cannot grant request specificity or create
missing measurements. Existing v5 optional CQL penalty must not be duplicated.

## Proposed decision, Phase1 implemented subset

Keep a separately invoked `rl_defense.research` package with an internal versioned
research adapter reusing canonical `shared.EvidenceRef`. No public/shared contract or
API change, no import from existing training/serving paths. Express raw measured reward
and benign cost separately, preserve original reward, mark unknowns, pin provenance
and enforce analysis-only splits. Historical data is read-only; new measurements have
a new explicit semantics/config/source identity.

A research-only capability profile excludes actions with no relevant live effect;
shielded v6 is labeled separately. Fixed baselines and complete raw request evidence
check the measurement pipeline. This is not a learned candidate or a promotion gate.
No new action, trained cost critic, CPO/CQL implementation or training in this phase.

[Phase1 audit](../research/constrained-rl-phase1/AUDIT.md),
[CMDP proposal](../research/constrained-rl-phase1/CMDP.md),
[action matrix](../research/constrained-rl-phase1/ACTIONS.md),
[architecture comparison / no-go gate](../research/constrained-rl-phase1/DECISION.md).

## Consequences and ratification needed

V6 stays unchanged. Backend policy worker continues recommendations only. Expected
model cost constraints are statistical and cannot widen scope/permissions, authorize
execution, or replace independent seven-agent verification and human approvals.
A future cross-component experience contract needs owner review and shared codegen;
new action semantics require a new layout version without changing old indices.

No-go for constrained-DDQN/CQL training now. Conditional preference is a minimal
cost-aware DDQN ablation after feasibility/state/data gates. Broader amendments to
ADR0008/0014 require explicit owner ratification; they are not silently rewritten here.
