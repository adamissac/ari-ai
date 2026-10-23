# Phase 1 architecture decision and Phase 2 gate

**NO-GO now for either a new constrained DDQN or discrete CQL prototype. Phase2 is
not started.** Existing reward/cost measurement is sufficient for descriptive analysis,
but it does not establish state sufficiency, safe action support or a feasible policy
under an agreed damage budget. The two-intervention heuristic preserves availability by
leaving most attacks successful. Algorithm replacement is not a fix for that tradeoff.

## Compared architectures

| Architecture | Benefits / discrete-action compatibility | Required data and complexity/stability | Weaknesses, lab/seven-agent fit and evidence gate |
|---|---|---|---|
| A. Existing masked Double DQN | Implemented online/target masked argmax, replay and abstention; direct fit to25 discrete actions; frozen v6 is reproducible | Existing scalar-labelled lab/sim records; lowest additional complexity; bootstrapping/exploration/scale and validation selection already tested | Scalar reward trades defense against collateral damage; partial state, no efficacy-aware universal mask or explicit cost budget. Remains comparison/reference only. Seven-agent findings may supply reviewed context, not rewards or direct execution. V6's original gate does not validate new distributions |
| B. Cost-aware/constrained Double DQN | Reuse discrete architecture and evaluate separate reward/cost estimators; simpler controlled ablation than replacing policy class | Consistent r/c semantics, complete masks/control/budget history, coverage and held-out feasibility checks; moderate effort for separate cost targets, conservative action selector and possibly dual update | Ordinary Q bootstrapping can extrapolate offline; dual/penalty tuning may oscillate and average feasibility can hide per-scenario harm. A penalty alone is not a CMDP guarantee. Current lab can measure channels but must first show feasible controls; future seven-agent input stays artifact-only, independently verified. **Preferred conditional first prototype after readiness gate**, not approved now |
| C. Discrete CQL plus separate cost estimator | Matches discrete actions; reward pessimism can reduce unsupported-action optimism | Frozen mixed-policy coverage dataset, support diagnostics, current/next masks, separate calibrated cost data and evaluation. More complexity: regularization strength, masks, reward/cost calibration and data heterogeneity | A reward lower bound does not upper-bound damage. Pessimistic cost values would be unsafe; a cost upper bound needs separate justification. Deterministic demonstrations/noop dominance and aliased states remain. Existing v5 CQL penalty is already implemented and rejected historically; new training must not duplicate it. Same lab/artifact boundaries; no CQL-specific permission. **No-go before stronger data and comparison to B** |
| D. Hierarchical defense policy | Separate detection/eligibility, narrow deterministic controls, duration and high-level budget selection; could preserve authorization semantics and retain discrete low-level options | Request ownership/grants, verified narrow controls, option initiation/termination, semi-Markov duration and independent positive/negative tests. Highest engineering/credit-assignment burden | Error propagation, nonstationary subpolicies and long-duration cost attribution; authority cannot live in a learned high-level controller. Seven agents remain deterministic-orchestrator specialists, not RL subagents. Require proof narrow controls preserve own/delegated behavior, then show hierarchy adds value beyond a fixed access-control patch. Long-term proposal only |

## What the requested papers justify, and what they do not

[Achiam et al., CPO (2017)](https://arxiv.org/abs/1705.10528) motivates explicit expected
cost constraints and policy-update bounds. Its constrained policy-search analysis is
not a drop-in proof for masked replay DDQN with partial observations or fixed historical
data. We borrow the separation of objective and constraints, not an online CPO trainer.
Hard authorization remains independently enforced code.

[Kumar et al., CQL (2020)](https://arxiv.org/abs/2006.04779) addresses offline value
overestimation under distribution shift using conservative reward-value learning. It
supports considering discrete CQL **after** auditing coverage. Reward conservatism does
not imply conservative cost estimates or a request-availability guarantee. The repo's
existing optional all-action CQL gap lacks an explicit measured-cost channel/current
capability-mask objective, so turning on its coefficient is not a constrained solution.

[Fujimoto et al., BCQ (2019)](https://proceedings.mlr.press/v97/fujimoto19a.html) shows
why off-policy methods can fail from extrapolation outside a fixed batch and motivates
restricting behavior to supported actions. Its introduced algorithm is for continuous
control; our25 discrete actions call for a coverage/eligibility analysis, not copying its
continuous action generator. A capability mask and a behavior-support restriction solve
different problems; an executable action can still be unsupported by the dataset.

[Lin et al., TREBI (2023)](https://proceedings.mlr.press/v202/lin23h.html) studies offline
trajectory-based real-time budget adaptation. That motivates retaining complete cost-
labelled trajectories and explicit budget context. We have neither a validated trajectory
distribution model nor adequate budget/coverage data to transfer its results. Dynamic
expected budgets are distinct from deterministic authorization and per-step permission.
No diffusion/trajectory model is implemented in Phase1.

These are architectural inferences from the papers, not experimental validation of
any algorithm on Ari. Paper claims depend on their assumptions; none eliminates our
fixture limitations, ownership uncertainty or collateral damage automatically.

## Exact next move, outside this phase

1. Propose a telemetry/state/behavior contract and a feasibility-only lab protocol.
   Measure complete control timers/budget/history, own/delegated denial attribution,
   action support and behavior likelihoods where known. Test partial-observation/history
   alternatives without leaking generator intent. Do not reuse exposed holdout as fresh.
2. Independently verify a proposed narrow authorization-aware control (or application
   patch) against unauthorized, own-object, delegated and unknown-context requests.
   Compare deterministic controls first; principal-wide blocks may be fundamentally too
   coarse. Hard action capability/scope constraints never become reward penalties.
3. Before any model, owner agrees B/I and per-scenario compromise/availability thresholds,
   confidence criteria, dataset/split/seed provenance and stopping rule. Demonstrate a
   feasible deterministic baseline and supported alternatives under those thresholds.
   No numerical safety budget is invented from Phase1 results or retrospectively tuned.
4. Only after those gates and separate authorization: propose **one** bounded cost-aware
   DDQN ablation using separate r/c targets and a conservative constrained selector,
   compared with frozen v6, fixed rules and narrow deterministic control. If offline
   extrapolation remains material with adequate coverage, then compare the existing
   discrete CQL mechanism plus a justified separate conservative cost estimator.

No Phase2 code/training, candidate registration, customer-facing action or deployment
is included or authorized by this decision. Existing recommendation behavior and v6
champion metadata/weights stay unchanged.
