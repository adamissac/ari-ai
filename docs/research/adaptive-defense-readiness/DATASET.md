# Feature and trajectory readiness

The executable fixed-train-only inventory is DATASET_AUDIT.json. Input evidence roots
are SHA256 anchored in `adaptive_readiness.py`; each consumed artifact has a canonical
EvidenceRef with its byte hash. It reads no holdout or validation trajectories, starts
no app/policy, and writes no historical file. It verifies hashes, strict shapes,
episode chains/end flags and the saved derived report. Historical execution-source
and runtime proof is not rerun by this inventory; do not inflate its claim.

Phase1: 140 training episodes / 4,200 transitions. All current masks, raw measured
aggregate costs and delegated aggregate costs are recorded; behavior probabilities
known: zero. The candidate's clock-domain provider snapshots/arrival records: zero.
Duration training: 280 episodes / 8,400 transitions. First current masks missing:
280. Later current masks follow a validated preceding next-mask, but are not new
observations. Exact changing behavior probabilities and delegated costs are absent.
Do not pool these archives: familiar train_v8 scenario/seed identities overlap.
The inventory deliberately does not decode newly exposed holdout or simulator
results to manufacture a new dataset. Larger historical v6-v10 logs are described
in the preceding Phase1 audit and keep their original evidence indices; they are
not silently certified as candidate-compatible by this narrower count audit.

Field-level assessment:

- Existing normalized obs/next_obs: present with old layout; candidate freshness,
  exact grant validity, knowledge arrival, complete control timers/history/budget
  absent. All 32 candidate feature contracts lack full historical decision-time
  coverage; OBSERVATIONS.md separately identifies partial legacy proxies. Shape
  conversion cannot reconstruct unavailable facts.
- Action, reward, next mask: present. Proposed action/rejection absent in old live
  transitions because invalid proposals became noop. New Phase1 current masks are
  explicit; duration first mask missing. Candidate five-slot mask is incompatible.
- Behavior policy: policy name/pinned configs and global checkpoint/epsilon metadata
  exist in relevant historical manifests. Per-choice actor/version/tie-break and
  selection likelihood are not fully logged. Missing propensities stay null; no
  probability one is invented from an action being observed.
- Reward provenance: old scalar/components and successful attack-labelled foreign
  reads measured. These are fixture metric labels after the action, not policy
  input or adaptive benefit under the repaired authorization guard.
- Cost provenance: aggregate benign denials measured. Phase1 retains request records
  and static grant configuration for descriptive delegated counts; duration lacks
  that split. Exact new-provider owner/delegate/unknown timing is not recoverable.
  Simulator hidden-stage weighted disruption is a different synthetic quantity.
- Retrospective/untrusted: attack_active/is_attack are generator evaluation truth;
  scenario names/schedules and future permission facts are inadmissible inputs.
  Client claims and agent prose cannot authorize reads or label exploit success.
- Episodes/seeds/splits: explicit Phase1 identities and complete chains checked;
  duration policies/seed bands, end flags and chains checked. Full historical
  scenario/runtime verification remains a separate pinned verifier responsibility.
  Selected prefixes and full logs cannot become independent examples.
- Counterfactual support: no coverage claim for unobserved actions. Known deterministic
  policies provide no alternatives' support; missing actor state cannot be repaired
  by a global epsilon. No counterfactual outcome is imputed from a recorded noop.

Permitted uses:

1. Supervised modeling: compatible old observations can support narrowly labelled
   descriptive/predictive on-policy outcome work after grouped train-only splits;
   this assessment does not train or claim causal transport to candidate state.
2. OPE: not ready for likelihood-ratio estimates; propensities and adequate support
   missing. Fitted estimators would need a separately validated model/support/error
   design and do not bypass partial observability or missing causal costs.
3. Offline RL: not ready for a safe-improvement claim; candidate semantics/context
   and action support missing. CQL cannot create missing data.
4. Online RL: logs alone cannot establish a valid environment. The residual task,
   controls, measurements and constraints fail readiness; no training authorized.

New collection is required only if the owner chooses a defensible residual task.
Required instrumentation and the blocked collection/preregistration protocol are in
PREREGISTRATION.md. No new empirical collection is executed in this phase.
