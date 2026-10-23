# Offline dataset readiness

Verdict: **ready for descriptive on-policy measured reward/cost analysis of compatible
live records; not ready for an honest safe-offline-policy claim or deployment**.
New Phase1 request records improve attribution but provide little action coverage.

## Available and missing evidence

- Historical `StepOutcome` has attack requests/successful attack foreign reads, legitimate
  requests/defense denials, attack-active for metrics, action, original scalar/components
  and terminated/truncated. Reconstruct raw negative compromise reward and legitimate
  denial cost directly from counts; never inverse-fit costs from a scalar reward.
- Original transition has s,a,s',nextmask,done. Subsequent current masks follow from the
  preceding nextmask after chain validation. The first current mask is missing. A guessed
  mask from approximate features is not a measurement. Original proposed invalid action
  was replaced with noop and is unrecoverable from an applied-only record.
- `experience.collect` records scenario hash, train split, seed, step and global behavior
  kind/epsilon/checkpoint/seed, file hash/source. Online experience has kind/scenario/
  split/seed/step and checkpoint selection lineage. Manifests/configs are necessary to
  bind semantic versions. Historical current first masks, detailed timers, decisions'
  propensities and changing behavior-network versions are absent.
- Aggregate delegated denial attribution is unknown. A legitimate delegate's foreign-body
  response is not an attack; gateway `compromised` alone is insufficient. New lab evidence
  preserves request intent flag, principal/owner, grant config and block reason, so the
  research adapter can independently calculate delegated denial. These are fixture
  identities/test data; production telemetry must remain pseudonymous/aggregated.
- Simulator disruption is synthetic hidden-stage/criticality weighting. It cannot be
  imported as measured legitimate request cost. Simulator and live records cannot be
  pooled under this schema's measured semantics.

## Implemented compatibility adapter

`rl_defense.research.dataset.load_legacy` reads existing episode JSONL/gzip or flat
experience JSONL with explicit external expected SHA256, policy and exact scenarios.
It checks byte hash, train/explicit-analysis-validation split, scenario hash when saved,
registered seeds/horizon, strict transition shape/accounting, complete chains and no
repeated (policy,scenario,seed,t). If historical scenario hash is absent (duration
archives), the **caller supplies** the scenario mapping pinned by the original RUN.json;
that is a documented provenance dependency, not recovered telemetry. Flat online logs
with reused seeds/episodes or out-of-registered-seed streams are deliberately refused:
first provide an independently indexed episode/run mapping, never guess boundaries.
Old full-log and selected-prefix records overlap and must not be concatenated.

`ResearchTransition` is an internal experiment adapter using canonical shared
`EvidenceRef`; it does not replace `shared/` or add a bus/network contract. Unknown
measurements require a reason; missing required measurements fail schema validation.
The old scalar remains alongside versioned new objective definitions. A future
platform ExperienceDataset contract needs owner review/codegen before integration.

## Statistical and offline-learning limitations

Counterfactual evaluation is not "replay actions against saved outcomes". Importance
sampling needs action likelihood ratios and support; deterministic baseline logs have
no support for actions not chosen. Global epsilon may only suffice with exact actor
checkpoint, masks, abstention rule and decision timing. The online actor changes between
episodes; absence of those pins prevents reliable historical likelihood reconstruction.
Behavior likelihoods are not strictly required to implement every offline Q-learning
algorithm, but insufficient coverage and partial observation still invalidate a blanket
safe-improvement claim. Fitted Q evaluation would need held-out independent data and
model/support-error diagnostics; it is not implemented here.

Split by immutable run/scenario/seed/episode groups **before** learning and keep selected
prefix/full-log overlap together. Different policies on paired exogenous seeds are
comparators, not independent replications; windows and overlapping trajectories are not
samples. New intervals resample whole seed clusters, stratifying by scenario membership;
a shared seed across scenarios remains one cluster. They describe evaluation randomness
for fixed policies, not training-seed uncertainty. Null denominators or incomplete cost
coverage remain null; no undefined bootstrap draws are silently removed.

The140new baseline episodes reuse familiar train_v8 scenarios/seeds. Old duration
training logs overlap these seeds; never pool them as independent data. No validation
or holdout result is relabeled as training. V6–v10 holdouts are exposed; no selection or
new safety claim can be based on treating them as fresh. The new dataset contains
shielded action semantics and a different severity context from original v6; keep its
manifest identity separate from the old logs.

## Before any Phase2 prototype

Require a reviewed dataset specification with explicit current/next masks, proposal /
applied actions, full operator-visible control/budget state, reward/cost definitions,
request/grant instrumentation version, immutable source/config/actor/behavior metadata,
known-vs-unknown costs and duplicate-free split lineage. Collect only in separately
authorized owned labs, with an explicit fixed behavior/support design if collection is
approved later. Measure coverage by action/state/context/scenario and cost tail, not just
transition count. Validate history/Markov approximation and counterfactual controls via
independent positive, unauthorized and delegated checks. Precommit feasibility thresholds
and uncertainty before model selection. None of that authorizes training in this phase.
