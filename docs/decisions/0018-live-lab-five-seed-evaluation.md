# ADR-0018: Five-seed evaluation for the isolated live lab

- Status: Proposed (owner review required)
- Date: 2026-10-20
- Context: docs/17 fixes DefenseSimEnv-v0 and five training seeds; past live-lab studies
  used request metrics, different split seed bands and one training seed.
- Proposal: live-lab studies preregister five training seeds, equal budgets,100 paired
  evaluation episodes/scenario, complete baselines/raw trajectories, seed-level CIs,
  multiple-testing correction and failure cases. Request compromise is not simulator
  impact; do not invent simulator time-to-containment from request telemetry.
- V9 is experimental lab evidence under its committed preregistration, not a claim to
  satisfy the unchanged simulator benchmark. Docs/17 remains in force for that benchmark.
- No study authorizes policy promotion or enforcement outside the owned demo app.
