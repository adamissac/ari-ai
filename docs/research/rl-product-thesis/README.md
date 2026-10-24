# RL feasibility, control expressiveness and product thesis

**Primary recommendation C — DEPRIORITIZE RL as a near-term product dependency.**
Research verdict: the tested resource controls failed, but fundamental infeasibility
and optimal existing-action performance remain unresolved. Product recommendation:
deliver non-RL assurance and response capabilities first (Architecture C), keeping
Architecture B as the boundary for any later validated learned recommendation.
Training authorization: none. Customer pilot readiness: not established here.
This is a research/product recommendation, not an accepted change to the master
spec, automatic removal of RL, or authorization to change enforcement.

## Five explicit answers

1. **Is safe defense physically achievable? Unknown under the full constraints.**
   Legitimate demand alone is not excluded by the computed necessary bounds. That
   is not a feasible admission/scheduling witness: queues, nonpreemption, deadlines,
   latency and separate denial/timeout caps still apply.
2. **Could any existing-action controller satisfy them? Unresolved.** All four
   eligible-budget rules fail in every attack family. We did not solve the
   full-future existing-action optimization, so cannot conclude all policies fail.
   Persistent-static is outside that action-duration budget and also fails attack
   availability. Its improvement is not a safe feasibility certificate.
3. **What is the primary limitation? Demonstrated aggregate overload and coarse,
   intermittent actuation; their relative causal contributions are unidentified.**
   Source/route overlap and partial observations compound the problem. No controlled
   capacity, action-granularity or information ablation identifies a single cause;
   blaming the neural policy or asserting capacity alone is unjustified.
4. **Is RL justified over strong non-RL methods? Not on current evidence.** A real
   sequential mechanism exists, but no safe residual advantage over conventional
   methods has been demonstrated for this task. Do not train to repair an unknown
   feasibility or missing-information problem.
5. **Should RL remain Ari's primary differentiator? No, as a near-term product
   dependency.** The defensible technical thesis is shared, version-aware intended
   behavior, executed evidence, independently verified remediation and monitoring.
   Customer differentiation/value remains a hypothesis requiring customer evidence,
   not something established by simulator benchmarks.

## Audit and evidence matrix

Audited main base e13e237a (includes PR434); analytical source is pinned in the new
[bounds output](bounds/BOUNDS.json). No historical report, protocol, dataset,
checkpoint, deployment default, promotion record or control contract was edited.

| Claim | Evidence | Status / strength | What it does not establish |
|---|---|---|---|
| Real DDQN exists | [agent source](../../../rl-defense/rl_defense/agents/ddqn.py), online selection/target evaluation, replay, gradients | Implemented algorithm; source inspection | Constrained costs, safe exploration, useful task or production benefit |
| Payment-read guard uses trusted application authority | PR388/414; [foundation audit](../constrained-rl-phase1/AUDIT.md), [provider](../../../rl-defense/rl_defense/research/authorization_provider.py) | Authored executable guard/provider cases and schema tests | External customer provider integration or population security guarantee |
| Authorization RL readiness was NO-GO | PR422 [decision](../adaptive-defense-readiness/DECISION.md) | Documented missing residual task/data/efficacy | No RL could ever help any cyber task |
| Finite queue/control effects are implemented | PR430 [design](../resource-exhaustion/DESIGN.md) | Unit-tested modeled work, delay, harm and cutoff | Calibrated CPU/HTTP service or strategic adversary |
| Five tested controls fail attack-family acceptance | PR433 [formal report](../resource-exhaustion/feasibility-001/REPORT.md) | One preregistered600-episode study, raw sealed records | Infeasibility of all possible controllers |
| Aggregate offered load exceeds physical supply in attack families | New120-record demand inventory below | Exact finite-record arithmetic | All offered adversarial work must be consumed |
| Necessary completion upper bounds do not exclude90% | [methodology](METHODOLOGY.md), bounds output | Proven optimistic inequalities evaluated on archived jobs | Feasible oracle, safe schedule or achievable latency |
| Existing actions have limited coverage and broad targets | Source plus overlap/coverage arithmetic below | Cap proof and recorded identity overlap | Causal attribution of the observed failures |
| V6 historically beat its selected teacher | [v6 report](../../../rl-defense/results/live-retrain-v6/REPORT.md) | Owned in-process lab: return−5.30 versus tuned rules−7.58 | Beats every conventional rule or solves current task |
| A stronger fixed v6 reference did better on return | [v6 provenance](../../../rl-defense/results/live-retrain-v6/PROVENANCE.md) | always_block_principal_long−3.89, with availability0.945 vs candidate0.952 | Unqualified dominance across all objectives |
| Historical provenance limits remain | Same v6 provenance |153,000 complete rows vs108,000 available at selection,60 skipped updates; original bytes restored | Retroactive correction of historical lineage or new holdout freshness |
| Later training did not establish promotion | [v10 provenance](../../../rl-defense/results/live-retrain-v10/PROVENANCE.md) | Ten seeds retained; primary hypothesis unsupported; every candidate rejected by a gate | Every future algorithm will fail |
| Shadow plumbing exists, not executed protection | [API](../../../backend/backend/api/live_defense.py), [policy](../../../backend/backend/live_defense/policy.py), [Phase6 audit](../../LIVE_DEFENSE_PHASE6_READINESS.md) | Implemented NOT_EXECUTED decisions, independent gates; prior owned-test evidence | Customer effectiveness, current deployment health or pilot readiness |
| Shared intelligence/verification supports a non-RL thesis | [master product spec](../../01_MASTER_PRODUCT_SPEC.md), [intelligence](../../../code-intelligence/README.md), [review](../../../code-review/README.md), [host](../../../backend/backend/host.py) | Spec plus implemented provenance, tests, independent Verify gates | Validated customer ROI, analyst accuracy or competitor superiority |

The v6 result is positive historical learning evidence, not erased because later
studies failed. It is a different55-channel/25-action lab objective, versus the
73-channel/three-action resource task. Its teacher-relative gain, stronger fixed
reference, harm tradeoff and exposed holdouts must travel together. The current
DDQN optional CQL/DQfD losses do not supply missing cost constraints or causal data.
No model/checkpoint is loaded or evaluated by this assessment.

## Mathematical capacity model

For archived request i: release r_i, required integer work p_i, completion c_i and
absolute deadline d_i=r_i+24. Two workers supply at most2 units/tick, one request
per worker; unfinished jobs wait in FIFO order, at most12 waiting plus2 in service.
A timely completed job needs its entire p_i processed in [r_i,d_i]. Accepted jobs
can time out after partial work. Rejected work consumes no backend worker units.
Intervention overhead consumes actual capacity. All such restrictions remain in
force in the real model; the analytical upper bounds relax them as stated.

There are240 decision ticks: capacity480 worker-ticks. The no-arrival/no-control
settlement allows at most24 additional ticks: an optimistic total528. It contributes
real completions/work/timeouts, not extra control decisions. Per-family acceptance
requires completion>=90%, denial<=5%, timeout<=5%, completed mean latency<=16,
applications<=4,active ticks<=64,overhead<=4. There is no approved numeric cap on
adversarial work; minimizing consumed adversarial work is the security objective.
All acceptance metrics must hold together; completion alone is insufficient.

For N legitimate jobs, minimum demand for ceil(.9N) completions is the sum of that
many cheapest legitimate costs. For every interval I=[a,b], jobs entirely confined
to I require their processing within its2(b−a) supply. If only k cheapest confined
jobs fit, C*<=N−|J_I|+k. Enumerating release/deadline endpoints yields the necessary
upper bound used here. Proof: at most k confined jobs can fit even after removing
all other jobs and relaxing FIFO/buffers; at most N−|J_I| others can complete.
These bounds hold for any physical policy. They neither produce a feasible
nonpreemptive schedule nor solve legitimate-denial/timeout/latency constraints.

The following are exact archived means per workload, not population estimates.
"B witness" is a hindsight per-record maximum completion among four budgeted
rules; it is not one deployable controller and ignores other safety failures.
"Upper" is the ratio of summed interval-cardinality upper bounds to offered
legitimate count. No confidence intervals or new bootstrap were computed.

| Family | Legit work | Adv offered work | Total offered work | Cheapest90% legit work | B witness completion % | Relaxed upper % |
|---|---:|---:|---:|---:|---:|---:|
| high_exhaustion | 359.80 | 1968.20 | 2328.00 | 273.50 | 32.40 | 100.00 |
| legitimate_burst | 466.85 | 0.00 | 466.85 | 357.75 | 97.06 | 99.22 |
| low_exhaustion | 359.10 | 283.30 | 642.40 | 272.35 | 84.30 | 100.00 |
| mixed | 436.40 | 1129.35 | 1565.75 | 331.80 | 44.06 | 100.00 |
| shifting | 361.15 | 603.60 | 964.75 | 274.95 | 76.83 | 100.00 |
| stable | 364.65 | 0.00 | 364.65 | 278.15 | 100.00 | 100.00 |

No individual archived workload has a computed completion upper bound below90%.
Burst traffic does have binding deadline intervals (aggregate upper99.22%), showing
why total work alone is not enough. In high exhaustion total demand2328 exceeds
528 by4.41× while legitimate work359.8 does not. Mixed legitimate demand436.4 is
also below528. Thus total offered-load infeasibility is proven if *all* work must
finish, but that is not the registered goal. No claim of achievable90% legitimate
completion, latency or safe oracle is supported by these necessary checks.
A lower witness below90% and an upper bound above90% leave feasibility unresolved.
The physical impossibility of serving every request cannot be substituted for the
unproven impossibility of selectively serving legitimate requests.

## Three oracles and solver status

- **A, perfect-information admission:** nondeployable, privileged labels. We have
  a mathematical necessary upper bound and observed completion lower witnesses,
  not a solved oracle. Ignoring denial limits and dropping difficult jobs makes
  the upper bound optimistic; a feasible relaxed allocation would still not prove
  safe FIFO/queue behavior. No optimizer was run, and no optimality certificate
  or actual schedule is claimed.
- **B, full-future existing actions:** valid schedules retain delay,duration,
  cooldown,source selection and budgets. Best observed budgeted traces are only
  lower witnesses for its completion objective. Its exact optimum and joint safe
  feasibility remain unknown. Arbitrarily targeting any source would already
  relax the real previous-consumed-work selector; replaying noop telemetry for
  other actions would be invalid counterfactual state substitution.
- **C, observation-limited:** only prior73-channel observations/known bits/masks.
  Tested rules are instances, not a solved optimum. Remaining job demand and
  adversarial labels are unavailable at decision time; the future and label
  privilege in A/B cannot leak into C, training or serving. No exact C solver,
  policy, forecasting model, counterfactual simulator or new dataset was built.

The supplied bounds do not separate explanation1 (fundamental infeasibility) from
explanation2 (insufficient control/observability/tested policy). Explanation3 is
supported only in its weak sense of a measurable sequential mechanism, not a safe
residual optimization opportunity warranting RL. An exact oracle, capacity
ablation or alternative-controller rollout would need a new approved registration;
none was performed. Research uncertainty is not a product case for another run.

## Control expressiveness

Four applications × two windows × eight ticks = at most64 active ticks, or8/30
windows (26.7%). At least22 windows are unprotected by a limiter; pending delay,
expiry/cooldown and budget bind scheduling. This is a proven duty ceiling, not a
proof that controls cannot prevent persistent queue pressure indirectly.
Route limiting caps route1 at2 matching offered requests/window. Source limiting
caps one previous-work-selected source at3; only one control may be pending/active.
Neither sees per-request abuse intent or future demand, and admitted backlog is
not removed by activating a limiter. All users are permission-valid in this task.

| Family | Legit route1 jobs % | Adv route1 jobs % | Adv sharing source/window with legit % | Optimistic removable adv offered work | Unfiltered adv offered work lower |
|---|---:|---:|---:|---:|---:|
| high_exhaustion | 29.90 | 79.33 | 75.75 | 589.50 | 1378.70 |
| legitimate_burst | 30.25 | undefined | undefined | 0.00 | 0.00 |
| low_exhaustion | 29.40 | 81.50 | 78.25 | 105.85 | 177.45 |
| mixed | 29.78 | 79.94 | 61.54 | 352.10 | 777.25 |
| shifting | 29.97 | 78.55 | 77.13 | 425.10 | 178.50 |
| stable | 29.60 | undefined | undefined | 0.00 | 0.00 |

Overlap is a finite-record description, not a classifier impossibility theorem.
Route1 carries about30% of legitimate jobs and roughly79–82% of attack-family
adversarial jobs. Shared source/window identities are common, so denying a scope
cannot directly separate intent. Legitimate burst traffic itself triggers harmful
control: resource-aware denial7.38% in433 versus the5% cap.

The offered-work bound gives an unrealistically favorable controller any source
or route1, zero collateral, total rejection of the selected scope, arbitrary8
windows and no quota/delay/cooldown restrictions. Even that relaxation cannot
filter all offered adversarial work. In high exhaustion at least1378.7 offered
adversarial units remain on average. **This is not consumed work:** capacity
rejection/timeouts can discard it, so comparing it to528 cannot prove safe service
impossible. No consumed-work/resource-success conclusion is inferred from it.

Broad scopes, one-window activation delay, two-window expiry and64-tick cap are
structural limitations. Whether any one is decisive needs separately approved
analysis/measurement. More capacity would raise supply but could still be saturated
by the flood; no capacity-response experiment was run. Work-aware scheduling may
reduce head-of-line delay, but true future work/intent is not currently observable.
None of these alternatives is an implemented or approved customer control.

| Proposed direction | Potential benefit | Prerequisite / main risk | Simplest candidate before RL |
|---|---|---|---|
| Per-request admission | Finer collateral control | Trusted decision-time facts; classification error | Deterministic application policy and quotas |
| Cost-aware scheduling | Less expensive-job head-of-line blocking | Cost estimate freshness, starvation and deadline fairness | Bounded fair scheduling / deadline-aware optimization |
| Adaptive concurrency | Match admitted work to service pressure | Cannot identify abuse by itself; controller stability | Measured feedback with hard caps |
| Queue management | Bound waiting and stale work | Discarding valid jobs still counts as harm | Explicit deadlines/fair queues |
| Circuit breaker | Limit cascading resource failure | Can deny whole legitimate routes; recovery policy | Deterministic failure/recovery thresholds |
| Static capacity expansion | More physical supply without identifying intent | Cost and flood scaling; no measured production demand | Capacity planning before policy complexity |
| Stronger feedback / predictive control | Anticipate pressure and delayed effects | Valid model, estimates and robust limits | Feedback, forecasts, then bounded MPC if necessary |

## Does learning add distinct value?

Authorization, invariants, fixed caps and approval remain deterministic regardless
of the optimizer. PR414 supplies owner/delegation/unauthorized/unknown classification;
client-supplied claims cannot become authority. No learning advantage is expected
for an exact permission lookup. Partial workload observation, delayed effects,
competing harm/cost objectives and stochastic source shifts *are* present in the
resource model. A strategically adaptive attacker and calibrated nonstationary
customer process are not established. Long-horizon allocation is a hypothesis of
potential value, not empirical evidence that a neural learner is needed.

Feedback rules are the first comparison for measured overload. Heuristic constrained
optimization can encode known budgets directly. Forecasts may anticipate arrivals
but must be validated using only past data. Receding-horizon MPC is a meaningful
competitor when dynamics/uncertainty can be modeled; model mismatch and online
compute remain costs. Contextual bandits suit decision problems with local feedback;
using them for this queue would require justifying neglected carryover. RL can
represent delayed returns, but neither that representational ability nor Double
DQN's value-estimation improvement establishes feasibility or safety here.

Method background: [Double DQN, original paper](https://arxiv.org/abs/1509.06461),
[Rawlings/Mayne/Diehl MPC text, sixth printing](https://sites.chemengr.ucsb.edu/~jbraw/mpc/MPC-book-2nd-edition-6th-printing.pdf),
[Li et al. contextual-bandit paper](https://arxiv.org/abs/1003.0146). These primary
sources motivate method families, not claims about Ari's measured performance.
The controller ordering above is an engineering recommendation, not a tested
ranking. No alternative has been shown to meet the current attack-family SLOs.

## Product architecture assessment

| Criterion | A: RL-first autonomous defense | B: deterministic enforcement + learned support | C: non-RL assurance and response |
|---|---|---|---|
| Core value | Learned detection/intervention allocation | Hard authority with optional bounded recommendations | Understand changes, validate findings, repair with proof, monitor regressions |
| Differentiation | Potential sequential optimization; currently unproven | Shared evidence and accountable recommendations; learned uplift conditional | Version-aware intended behavior shared across pillars and independent verification |
| Customer benefit hypothesis | Less threat damage with less disruption | Operator-visible recommendations without surrendering permissions | Fewer unsupported findings, reproducible fixes, less repeated triage |
| Research risk | High: task feasibility, distribution shift, constraints, evaluation | Medium/high for learner; deterministic boundary independent | Lower RL risk; detection/LLM correctness and workflow value still need validation |
| Operational complexity | Highest: learning, action safety, rollback, drift, causal telemetry | Significant: provenance, abstention, approval, optional model monitoring | Significant engineering, but no online learning dependency |
| Evidence required | Feasible task, strong safe baselines, independent holdout, reliable costs, intervention proof | Measured incremental recommendation benefit and independent authorization/audit | Exact-SHA intelligence, executed negative+positive tests, independent Verify, regression persistence, authorized operator validation |
| Explainability/trust | Opaque values and exploratory harm burden; reward not a safety proof | Explain evidence, scope, unknowns and rejected action; analyst acceptance is not execution | Concrete request/test/code evidence and reviewable patch; distinguish hypotheses from verified findings |
| Disadvantages | Present research does not justify deployment centrality | Extra complexity without value if recommendations add nothing | No proven learned adaptation; market differentiation/ROI unmeasured |
| Use cases | Long-term research only; no customer autonomy authorized | Future gated decision support after task-specific evidence | Near-term authorized repo assurance and human-approved remediation workflows |

Recommend C for near-term delivery, retaining B as an architectural boundary for
optional future learning. Do not market the current shadow system as autonomous
protection: decisions are NOT_EXECUTED; analyst acceptance does not authorize a
control. Existing owned-test execution grants/channels are separate, scoped and
not a customer rollout. This audit did not verify deployment health, customer ROI,
real-adversary effectiveness or a customer pilot, and declares none ready.

## One concrete non-RL milestone

**Proposed: exact-commit assurance-to-regression evidence packet.** Extend existing
shared intelligence/reviewer/independent Verify and monitoring pathways rather than
build another indexer, detector stack or policy agent. This is a proposal only.

For one explicitly authorized repository/scope and customer-approved behavioral
expectation, demonstrate the chain: commit-bound expectation → scoped reproducible
negative and authorized-positive checks → human-approved candidate patch → fresh,
independent Verify → stored regression tied to the exact base/head SHA → next
relevant change invalidates freshness and requests recheck. Reuse existing shared
contracts/API/job boundaries; never import another subsystem's internals.

Proposed acceptance: every verified claim resolves to executed evidence and the
correct snapshot; stale/unsupported results remain unknown or hypotheses; negative
and normal-authorized cases both pass after repair; failed/inconclusive Verify
cannot close a finding; no patch/model can approve, merge, deploy or execute a
runtime control itself. Measure analyst acceptance/rejection, false positives and
time-to-verified-resolution separately; numerical commercial targets require owner
and customer agreement before evaluation. Test mocks are not live-customer evidence.
Use existing offline fixture/integration suites first, then separately approve any
paid-provider, authorized sandbox or customer run with explicit budgets. Stop for
scope/freshness mismatch, authorization failure, missing evidence or budget breach.
No new implementation, customer access, paid calls or sandbox execution is launched
by this assessment. No RL experiment is proposed because primary recommendation C
is to deprioritize it; revisiting RL requires a newly justified residual task and
separate approved protocol, not relaxing feasibility001 after seeing its results.

## Reproducibility and limits

New bounds source0074562408b0c302e0c00f8a4226862bacdbaa7e; result SHA256
5e3fbd649031054e2c85815edd9b168d52cd737fa9204e644c1c9a54ea8f0262.
One read-only120-record pass took0.7621 seconds; peak RSS30,900,224 bytes. Source,
Python/platform, original index and all per-record bounds are retained. Input hashes
were verified before reading. No numerical solver or full-future oracle was run.
The exact tiny single-worker test checks the upper-bound inequality against brute
force mathematical schedules, not a traffic experiment. Further tests cover local
deadline overload despite enough total work, the insufficiency of a relaxed bound
for nonparallel scheduling, and the eight-window offered-work ceiling.

All historical studies remain exposed, not reusable as new final holdouts. Bounds
apply to the finite archived draws, not all possible seeds or customers. Every
uncomputed optimum and unmeasured customer claim remains explicitly unresolved.

[Verification and reproduction](VERIFICATION.md) records source/input/output identity
and executed checks. The methodological uncertainty is not hidden by passing tests.
