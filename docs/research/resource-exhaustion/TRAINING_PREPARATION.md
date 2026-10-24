# Stage2 preparation and final gate

**Training NO-GO.** A sequential queue/control mechanism is now implemented and unit
checked, but no approved comparative feasibility result establishes safe baseline
headroom. Physical capacity/arrival models are assumptions, constraints/sample/compute
values remain unapproved, and no training authorization exists. No pilot-readiness
or real-world-effectiveness claim follows from these tests.

Implemented preparation:

- Fixed physical normalization and73-channel observations, current/next masks,
  deterministic Gym seeding and independent offered-traffic RNG progression.
- Internal resource-experience/0.1 schema: environment/config hash/profile, episode,
  seed/step, frozen vectors, proposal/applied action, behavior rule and exact known
  probability1, separate raw reward/seven cost channels, finite-horizon flags and
  ordered decision/event cutoffs. Labels/scenario metadata are not tensor inputs.
- Bounded replay-shape buffer with separate reward/cost arrays. It refuses unit
  instrumentation when for_training=true. No cost critic/optimizer/gradient path.
- Evaluation-only microfixture runner, <=8 windows and fixture seeds0..9. Its CLI
  writes exactly one fixed mixed/seed0/four-window/threshold-rule receipt and refuses
  existing output. No study/holdout/sweep/training command is provided.
- Unit manifest pins source commit, package bytes, protocol, config, versions,
  Python/dependencies and every output hash, with canonical EvidenceRefs. Source
  must be committed; failures retain events/ledger/attempts and manifest. Source
  and HEAD are checked again after capture. This is scoped source provenance, not
  a complete binary dependency/container attestation.
- Read-only verifier uses an externally supplied index digest, strict transition
  shapes/chains and raw work/outcome/latency/control/overhead accounting. It does
  not replay a policy or certify production validity. Unit data is explicitly
  ineligible for training and cannot be turned into approval by changing a flag.
- Prospective checkpoint metadata must include environment/observation/action/config,
  actor/source/normalization IDs, optimizer/algorithm versions, training run lineage,
  dataset hashes, seed, step, weight hash and validation identity. No weight file is
  written here; unit manifests explicitly record checkpoint=null and gradients=false.

Algorithm recommendation: **no learning now**. If approved feasibility establishes
safe headroom beyond the strongest conventional reference, prefer a minimal
cost-aware Double DQN for this small discrete action set. Reuse the existing correct
online-selection/target-evaluation implementation, but a constrained variant still
needs independently reviewed cost heads, constrained action-selection/dual updates
and approved limits. Separate raw costs cannot be replaced with one opaque scalar.
Those learner changes are not justified/implemented before the feasibility gate.
Alternative constrained discrete Q-learning has the same evidence/observability
requirements. CQL is not justified by a four-window unit receipt; there is no
training-eligible offline dataset or counterfactual action coverage. Known probability1
under a deterministic rule provides no support for alternatives.

## Future training protocol proposal — not executable

Hypothesis: one fixed cost-aware DDQN improves the approved primary resource outcome
beyond the strongest eligible deterministic resource-aware/static policy while
meeting every family-specific safety/quality and operational constraint. No success
if a strong persistent conventional limiter dominates. No claim from aggregate return
alone. Require first the approved feasibility protocol and source/config freeze.

Propose five training seeds100..104, <=50,000 decisions each, one fixed hyperparameter
configuration, one CPU process, max30 minutes per seed and512MiB RSS. These are
UNAPPROVED proposals, not permission or a chosen compute allocation. Gamma1 for the
finite horizon; truncation ends the finite return. A continuing objective requires
a new bootstrap contract. Replay capacity50,000 and batch64 are provisional design
values; architecture/learning rate/cost-update rules must be reviewed and frozen
before any run. Do not sweep or inherit old v6 loss settings implicitly.

Development scenario families are already exposed. Proposed validation workload
seeds200..219 may support selection only after approval; a genuinely independent
final holdout needs separately authored mechanisms/parameters and an access registry,
not renamed old families or fresh seed numbers alone. It is not generated here.
Lock sample size/intervals after approved train-only precision planning; no holdout
variance for tuning. Report between-training-seed uncertainty and paired whole
workload-seed intervals, all costs/coverage/failures and per-family results.

Stop/retain all partial artifacts for constraint, accounting, cutoff, mask,
provenance, cleanup or compute failure. No automatic unfavorable-only reruns,
replacement seeds, adaptive sample extension, interim holdout use or checkpoint
promotion. Any future candidate may only produce research artifacts. Serving would
require a separate integration design, independent approval and immutable incumbent
pin; rollback would restore that pin, never silently overwrite v6. No serving
adapter, rollout, customer control or rollback execution is part of this phase.

Exact outstanding approvals: (1) service/workload/control assumptions and comparable
baseline profiles; (2) formal feasibility safety values/sample/seed/compute/statistics
and explicit launch; (3) feasibility finding of a meaningful safe residual gap;
(4) final learner/schema/normalization/splits/limits/training protocol review;
(5) explicit owner training authorization. Promotion/customer integration remain
separate and unauthorized even after a future training GO.


The bounded evaluation-only settlement helper drains outstanding jobs after controls
stop, without new arrivals or changes to prior observations. Formal comparison must
include this tail. Current unit transitions deliberately retain horizon-censored
outcomes and are ineligible for training; a reviewed terminal-cost collector must
attribute actual settlement outcomes to finite-horizon training returns before GO.
The existing DDQN mathematics is reusable, but its legacy disruptive-action mapping
is not this three-action schema; a future adapter must declare the two limiter
indices explicitly rather than inherit live/v6 semantics.
