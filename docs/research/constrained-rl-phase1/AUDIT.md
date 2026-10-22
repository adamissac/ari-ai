# Phase 1 architecture audit

Audited base: main `198eb3b96a13d5a83f93a42df4695b4384921dcc`.
Research execution source/tree and hashes are in the new result manifest. Historical
measurements are cited as historical evidence; no prior report/checkpoint is rewritten.
This is an owned in-process HTTP lab, not deployed enforcement or production evidence.

## 1. Observation construction and normalization

`rl_defense/envs/defense_sim.py:DefenseSimEnv._observe` emits48 features: five nodes
in `envs/config.py:NODE_NAMES` order (gateway,api,auth,payments,db), nine features each,
then time fraction, escalation budget fraction and escalation-pending bit. Alerts are
the five-step mean divided by10, anomaly is smoothed/noisy, monitoring is divided by
configured maximum; controls are booleans. All features are clipped to[0,1], float32.
Hidden stages appear only in `_info` metrics, not observations.

`live/loop.py:reset` first runs a real traffic warmup, builds facts, then clears records.
Warmup traffic establishes detector state but is excluded from episode metrics.
`live/telemetry.py:build_facts` uses measured per-window anomalous request counts
(cross-tenant attempt or forwarded application error); anomaly is the fraction times
monitor sensitivity0.5/0.75/1.0. `observations.from_platform_facts` divides alerts by10,
appends the same global features and clips. Live signals are single-window, unlike the
simulator's five-window history. Controls are advanced/ticked before next observation.

`layouts.py` fixes v2 at49features/23actions, v3 at55/25. v2 appends any-principal-block
active. v3 adds maximum remaining-block/long-duration, flagged-principal-count/3,
flagged-attempts/(6×flagged-count), flagged own-or-authorized share, previously-blocked
share and top-principal cross-attempt share. Capping loses volume information and
individual identity/grant/control timers. `LiveDefenseLoop._v3_features` never reads
`is_attack`. Platform `platform_mapping.principal_facts` uses equivalent reporter counts;
actual enforcement state stays zero because the product enforces nothing.
Tests: `test_env.py::test_observation_does_not_leak_hidden_stage`,
`test_live_retrain.py::test_telemetry_never_reads_the_generator_label`,
`test_live_v3.py::test_v3_features_describe_the_flagged_principals`.

## 2–4. Proposed actions, enforceable actions and masks

See [capability matrix](ACTIONS.md). Original indices remain unchanged. Simulator and
live masks mostly encode already-active controls, monitoring ceiling, pending
reassessment/finding severity and escalation budget. Principal masks come from the
previous window's flagged principal/node pairs and remaining durations, including
extension opportunities. They are **not** authorization checks or full efficacy masks.

`DefenseSimEnv.action_masks` and `observations.mask_from_facts` permit actions on nodes
with no relevant live traffic, and live escalation despite its missing containment
completion. `LiveDefenseLoop.step` replaces invalid actions with noop and loses the
original proposal; unlike simulator invalid-action penalties, it charges noop semantics.
The Phase1 shield is separate: only api/payments have traffic in the fixed existing
driver; exclude other node actions, escalation and scripted reassessment. Allow
monitoring's real sensing change even though it cannot directly contain attacks.
No historical indices or existing masks change. Shielded v6 is a different policy rule
using the same frozen network. Tests: `test_env.py::test_action_masks`,
`test_live_block_principal.py::test_block_is_masked_without_a_flagged_principal`,
`test_live_v3.py::test_raise_monitoring_has_no_containment_effect_live`, new
`test_constrained_research.py::test_capability_mask_excludes_ineffective_and_administrative_actions`.

## 5. Reward implementation and decomposition

Simulator `DefenseSimEnv.step` sums invalid-action, action/escalation cost, a hidden-
stage/criticality-weighted disruption proxy, adversary progression, containment, impact
and early-terminal continuation penalty. Its disruption is **not measured request
availability**; a benign node means hidden stage0, not "all requests authorized".

Live `LiveDefenseLoop._reward` is explicitly:
`-c_impact×compromised/max(1,attack_per_step)`
`-c_disrupt×benign_blocked/max(1,driver.benign_norm)`
`-c_action×1[action!=noop] -c_escalate×1[escalate]`.
`benign_norm` excludes stochastic extra delegate burst volume, so normalized disruption
can exceed one; do not invert scalar reward and call it a measured request fraction.
Default c_disrupt=.5; v4+ explicitly uses1.0 and delegation-aware detection.

Historical live `StepOutcome` contains actual request numerators/denominators, so reward
and cost **can be re-derived as raw counts**: reward=-compromised_reads,
cost=benign_blocked. This is a **new research objective**, not a claim to decompose all
old scalar rewards identically. Preserve original scalar/components. No counterfactual
"attacks prevented" label exists; lower compromise under paired exogenous traffic is
an outcome comparison, not per-request prevention ground truth. See [CMDP](CMDP.md).
Tests: `test_env.py::test_reward_components_sum_exactly_to_reward`,
`test_live_v4.py::test_c_disrupt_prices_a_blocked_legit_request_like_a_compromised_read`.

## 6–7. Legitimate damage, compromise and availability

`live/gateway.py:DefensiveGateway.request` records per-request actual HTTP status,
block reason, principal, resource owner, cross-tenant attempt and response-body foreign
customer_id. Allowed means **forwarded**, not HTTP-successful. A forwarded500 is not a
defense denial. Defense availability is1−benign defense-denials/benign requests; it is
not end-user successful-request availability, latency, monetary loss or SLA impact.

`LiveDefenseLoop.step` selects attacks by the **traffic generator's `is_attack` intent**,
then counts their actually successful foreign-body reads. This is executable fixture
truth; it is not a production attack label. `_is_compromise` alone can be true for an
**authorized delegated** foreign read; aggregate compromise correctly counts only the
attack-labelled subset. `PaymentsLiteInstrumentation.is_authorized_delegate` uses an
operator grant table; with `delegation_aware_detector=True`, delegated reads are not
flagged. An insider may make both authorized delegated and unauthorized reads.

`live/evaluate.py:episode_metrics/summarize` sum request counts before ratios:
compromised/attack requests;1−benign_blocked/benign requests; false disruption uses only
windows whose driver attack_active isfalse. False disruption can occur during attacks
too, but that harm enters overall availability rather than this quiet-only metric.
No-attack duty counts quiet windows with at least one denied benign request. Return is
mean episode scalar return, with a bootstrap over episodes. The new research metrics
keep undefined denominators null and cluster whole seed trajectories (see readiness).
Tests: `test_live_gateway.py::test_isolate_payments_disrupts_benign_payments_but_not_api`,
`test_live_v4.py::test_granted_read_is_not_flagged_and_ungranted_read_still_is`,
`test_live_validation_screen.py::test_principal_control_contains_rotated_tokens_but_also_blocks_authorized_reads`.

## 8. Episode endings and bootstrapping

Simulator terminates when db reachesimpact, charging the remaining-horizon impact plus
fixed terminal penalty; otherwise horizon truncates. Live never terminates on compromise:
`terminated=False`, `truncated=step_idx>=horizon`, `done=truncated`. Current live replay
uses done as terminal in `live/online.py:_add` and `live/retrain.py:_buffer`. Simulator
`agents/ddqn.py:NStepAccumulator` can distinguish termination/truncation. New research
records retain both flags. A finite-horizon30-window CMDP intentionally ends the return
there; a future continuing-task learner must not silently reuse this done convention.
Tests: `test_env.py::test_early_termination_is_not_cheaper_than_surviving`,
`test_live_loop.py::test_loop_produces_wellformed_transitions`.

## 9–10. Experience recording and offline readiness

`LiveDefenseLoop.step` records s_t before action, applied action, original reward,
s_(t+1), outcome and **next** action mask. `live/experience.py:collect` records scenario
name/hash/split/seed/t, behavior kind/epsilon/checkpoint/seed, dataset digest and source
commit in a manifest. `load_dataset` checks file hash and train splits, but not all
manifest schema/count/scenario consistency. `live/online.py:record` stores kind/scenario/
split/seed/t plus transitions; snapshots record complete and selected-prefix experience
lineage. It does not log every changing actor checkpoint/epsilon/propensity per decision.

No live `LiveTransition` request-level grant split, first current mask, full control
state/timers, behavior-action probability, proposal-to-applied mapping or versioned
reward/cost meaning is present in the old record itself. Some context is recoverable
from frozen source/configs/manifests; some is irretrievably unknown. Aggregate measured
benign cost is recoverable from compatible complete outcome records; separate own and
delegated costs are not. The new harness retains raw requests and grants/configs.
`research/dataset.py:load_legacy` is an analysis adapter, not a training or OPE consumer;
it verifies an externally supplied artifact hash and explicit configs, shape/seed/horizon,
chain/termination, reconstructs subsequent masks, and rejects overlapping trajectories.

See [dataset readiness](DATASET_READINESS.md) and executed readiness evidence.
Tests: `test_live_retrain.py::test_experience_is_train_only_and_hash_pinned`,
`test_live_v6.py::test_selected_snapshot_lineage_excludes_later_experience`, new
`test_legacy_read_only_hash_split_and_first_mask` / `test_duplicate_incomplete_and_broken_chains_rejected`.

## 11. Splits, seeds, hashes and holdout protection

`live/scenarios.py:LiveScenario` enforces train0..9999,val20000..29999,holdout40000..49999;
`config_hash` pins all scenario semantics while omitting new fields at their historical
defaults. `load_scenarios` validates directory-declared split but seed bands alone do
not prevent reuse across generations. Prior holdouts are exposed and cannot become
fresh selection data. Study source guards, observed budget/seed gates and full evidence
indices are in `live/study.py`, `live/evidence.py`, `live/online.py`. V9/v10 have frozen
preregistrations and complete saved outcomes; read them without rerunning holdout.
The Phase1 CLI loads only train_v8; legacy adapter admits validation only with explicit
analysis opt-in and always forbids holdout. It refuses incomplete or duplicate episodes.

Checkpoint loader verifies manifest/hash; backend `pipeline.verify_rl_checkpoint` pins
operator-trusted bytes before unpickling. `registry.Registry.promote` requires a
human identity, hash-pinned passing report/checkpoint, durable online evidence, actual
incumbent-bound baseline, nonempty passing checks and a servable layout. These are local
workflow controls, not a cryptographic two-person production authorization system.
Research imports no registry and never writes champion state.
Tests: `test_live_retrain.py::test_shipped_scenarios_use_disjoint_seed_bands`,
`test_live_v10.py::test_v10_splits_are_fresh_without_executing_them`,
`test_live_retrain.py::test_registry_report_integrity_and_incumbent_binding`,
`test_v6_evidence.py` (restored evidence), `test_constrained_research.py` boundary tests.

## 12. Markov sufficiency: not established

Both current policy inputs are partial observations. Simulator hidden attacker stage
changes transition probabilities while multiple hidden states share one observation.
Live bursts/active state, principal identities/grants, per-principal durations, rate-limit
request counter and warmup state influence next outcomes; the network sees aggregates,
booleans and only the maximum block duration. Clipping further aliases states. A noisy
observation vector is not proof of a Markov state, and adding a cost critic does not fix
this. Document the formulation as a partially observed CMDP approximation. Future
operator-visible history/control timers/budget and a validity/ownership-aware encoding
need an ablation; never expose generator intent or hidden future attack schedule.

## 13. Logged-trajectory policy evaluation

Descriptive on-policy cost/reward estimates are possible. Evaluating a *different*
policy requires overlap plus assumptions and either behavior likelihoods (importance
sampling/weighted or doubly robust estimators) or a justified fitted model/value
estimator with support/error analysis. Deterministic expert/v6 logs have zero support
for alternatives; online epsilon policies change during the run. A global epsilon and
checkpoint are insufficient without exact actor state/current mask/decision timing;
new baseline records intentionally leave behavior_probability null until an explicit
logging-propensity contract exists. Noop outcomes cannot be edited to mimic blocking.
Trajectory overlap, selected-prefix/full-log duplication and repeated snapshot evals
are not independent evidence. Phase1 uses fresh bounded **on-policy lab evaluation**
for baseline results, never invented counterfactual returns from logged data.

## Serving, earlier findings and ADR consistency

`inference.py:PolicyRunner` uses checkpoint greedy selection (including abstention),
Q-ranked confidence metadata and labeled shared recommendations. Backend
`pipeline.rl_recommend` loads trusted pinned bytes, derives facts from persisted
findings/monitoring/expectations, stores recommendation/explanation/audit, and executes
no containment. ADR0017 documents the quiet-window escalation gap under real severities;
this audit confirms the mapping and allows the research-only shield to test it without
changing served behavior. V7-v10 did not replace v6.

Historical v6 report confirms rounded return−5.30, rules−7.58, simulator−14.81,
availability95.2%, compromise18.5%. The quoted−3.89 baseline is **long** principal block
(and top-long tie), not generic fixed short block; do not confuse it with a new baseline.
V5 already has `DDQNConfig.cql_alpha`, an all-action logsumexp penalty in `DDQNAgent.update`
without current capability mask/cost critic. Its historical report rejected the candidate;
it is not a complete safe/offline algorithm and is not reimplemented or enabled here.

ADR0008 says offline simulator/recommendations only (proposed); ADR0014 adversarial
post-training still contains stale claims that a live lab does not exist; actual live
lab is implemented. These documents conflict in description of current implementation.
[ADR0019 proposal](../../decisions/0019-constrained-rl-foundation.md) explicitly raises
that mismatch and scopes this foundation to the existing owned lab, without silently
ratifying autonomous enforcement. ADR0018's five-training-seed learned-policy protocol
is not satisfied by this engineering baseline check. No real-world effectiveness,
production deployment, new training or seven-agent reward integration is established.

The new baseline's platform severity context is a deterministic **sample of values the
platform could produce**, not actual newly verified findings from the seven-agent team.
It is fixture context; the budgeted rule's severity prerequisite is tested against that
context and must not be advertised as independent finding validation.
