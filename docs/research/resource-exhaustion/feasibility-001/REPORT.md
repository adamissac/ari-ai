# Resource-exhaustion feasibility001 — formal results

**NO-GO for constrained RL training on the registered task.** Controls have measurable effects and delayed queue/control consequences, but no eligible policy meets the acceptance criteria in any attack-containing family. There is no demonstrated safe residual gap warranting training. This does not prove that every possible controller is infeasible.

## Execution and provenance

Exactly one launch, source `bed44ff27897225f3194c6afd118eee35f7516d2`:600 episodes,18,000 decisions,120 paired family/seed workloads, all five policies and all six families. No retries, seed replacement, parameter changes, training, checkpoint generation/promotion, reserved holdout or customer control. Full-lifecycle outcomes include bounded no-arrival/no-control settlement; zero unresolved jobs.

Collection, serialization, settlement,2000 bootstrap draws and sealing completed within the600-second budget: completion receipt9.178132 seconds and peak RSS79,462,400 bytes (75.78MiB), versus512MiB. One simulation/analysis process with numerical thread counts pinned1. These are observed process measurements, not proof of OS-enforced memory confinement. Budget checks poll peak RSS and a600-second alarm stops the runner. Post-run read-only audit is separate from study execution.

External SHA256 anchor of [STUDY_EVIDENCE.json](evidence/STUDY_EVIDENCE.json): `931fbd6737f963a1fe661ab029d08b7f4a26fe09e42805c291c9d1a1a2a0246c`. The manifest pins source files, protocol, config and runtime. Each compressed episode contains all observations/masks/actions, outcomes, raw jobs/work events, intervention ledger and settlement. A read-only audit verified every indexed digest,600 episode identities,18,000 decisions,120 paired offered workloads, work conservation, outcome totals, transition cutoffs, control costs and zero pending settlement.

## Every family and policy

Completion/denial/timeout fractions are ratios of summed full-lifecycle counts within each family. Latency is completed-request sum/count. Work is mean adversarial worker-ticks per episode. Operational caps apply to every episode; averages shown here do not override violations. All point estimates,95% bootstrap intervals, raw counters and all pairwise security contrasts are retained in [analysis](evidence/analysis.json) and [outcomes](evidence/outcomes.json).

| Family | Policy | Work | Completion % | Denial % | Timeout % | Latency ticks | Apps | Active ticks | Overhead | Violations |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| high_exhaustion | noop | 426.90 | 23.67 | 72.07 | 4.27 | 19.92 | 0.00 | 0.00 | 0.00 | completion, denial, latency |
| high_exhaustion | persistent_static | 346.30 | 62.03 | 37.97 | 0.00 | 13.16 | 1.00 | 240.00 | 1.00 | completion, denial, active_ticks |
| high_exhaustion | resource_aware | 424.35 | 26.00 | 70.53 | 3.47 | 19.58 | 4.00 | 64.00 | 4.00 | completion, denial, latency |
| high_exhaustion | static | 417.85 | 30.33 | 66.47 | 3.20 | 18.52 | 4.00 | 64.00 | 4.00 | completion, denial, latency |
| high_exhaustion | threshold | 410.05 | 31.63 | 64.93 | 3.43 | 18.32 | 4.00 | 64.00 | 4.00 | completion, denial, latency |
| legitimate_burst | noop | 0.00 | 96.18 | 3.56 | 0.26 | 7.97 | 0.00 | 0.00 | 0.00 | none |
| legitimate_burst | persistent_static | 0.00 | 92.31 | 7.69 | 0.00 | 4.07 | 1.00 | 240.00 | 1.00 | denial, active_ticks |
| legitimate_burst | resource_aware | 0.00 | 92.44 | 7.38 | 0.18 | 6.89 | 4.00 | 64.00 | 4.00 | denial |
| legitimate_burst | static | 0.00 | 96.23 | 3.59 | 0.18 | 7.00 | 4.00 | 64.00 | 4.00 | none |
| legitimate_burst | threshold | 0.00 | 96.41 | 3.56 | 0.03 | 7.43 | 2.25 | 36.00 | 2.25 | none |
| low_exhaustion | noop | 222.70 | 79.20 | 18.23 | 2.57 | 16.47 | 0.00 | 0.00 | 0.00 | completion, denial, latency |
| low_exhaustion | persistent_static | 194.15 | 87.30 | 12.70 | 0.00 | 6.91 | 1.00 | 240.00 | 1.00 | completion, denial, active_ticks |
| low_exhaustion | resource_aware | 218.55 | 80.53 | 17.43 | 2.03 | 16.24 | 4.00 | 64.00 | 4.00 | completion, denial, latency |
| low_exhaustion | static | 219.05 | 83.07 | 15.77 | 1.17 | 15.10 | 4.00 | 64.00 | 4.00 | completion, denial |
| low_exhaustion | threshold | 218.20 | 82.87 | 15.80 | 1.33 | 15.82 | 4.00 | 64.00 | 4.00 | completion, denial |
| mixed | noop | 359.10 | 35.67 | 60.56 | 3.78 | 19.41 | 0.00 | 0.00 | 0.00 | completion, denial, latency |
| mixed | persistent_static | 288.60 | 67.42 | 32.58 | 0.00 | 13.10 | 1.00 | 240.00 | 1.00 | completion, denial, active_ticks |
| mixed | resource_aware | 356.05 | 36.92 | 59.53 | 3.56 | 19.07 | 4.00 | 64.00 | 4.00 | completion, denial, latency |
| mixed | static | 343.30 | 42.64 | 54.42 | 2.94 | 18.14 | 4.00 | 64.00 | 4.00 | completion, denial, latency |
| mixed | threshold | 344.70 | 41.94 | 54.92 | 3.14 | 18.18 | 4.00 | 64.00 | 4.00 | completion, denial, latency |
| shifting | noop | 248.75 | 72.00 | 25.50 | 2.50 | 14.48 | 0.00 | 0.00 | 0.00 | completion, denial |
| shifting | persistent_static | 197.40 | 85.83 | 14.17 | 0.00 | 6.56 | 1.00 | 240.00 | 1.00 | completion, denial, active_ticks |
| shifting | resource_aware | 239.45 | 74.10 | 23.67 | 2.23 | 14.13 | 4.00 | 64.00 | 4.00 | completion, denial |
| shifting | static | 241.90 | 74.17 | 24.00 | 1.83 | 13.17 | 4.00 | 64.00 | 4.00 | completion, denial |
| shifting | threshold | 244.75 | 73.83 | 23.90 | 2.27 | 13.50 | 3.95 | 63.20 | 3.95 | completion, denial |
| stable | noop | 0.00 | 100.00 | 0.00 | 0.00 | 3.35 | 0.00 | 0.00 | 0.00 | none |
| stable | persistent_static | 0.00 | 96.23 | 3.77 | 0.00 | 2.92 | 1.00 | 240.00 | 1.00 | active_ticks |
| stable | resource_aware | 0.00 | 99.40 | 0.60 | 0.00 | 3.35 | 3.85 | 61.20 | 3.85 | none |
| stable | static | 0.00 | 99.13 | 0.87 | 0.00 | 3.27 | 4.00 | 64.00 | 4.00 | none |
| stable | threshold | 0.00 | 100.00 | 0.00 | 0.00 | 3.35 | 0.00 | 0.00 | 0.00 | none |

Persistent-static remains240 active ticks with one application and one overhead unit in every episode. It violates the64-tick cap in every family and is an unconstrained diagnostic, never a safe eligible reference. It also violates denial constraints in all families except stable, and completion constraints in every attack family. No outcome or violating arm was discarded.

## Equal-family aggregate summaries

These averages cannot certify per-family safety. Brackets are descriptive95% paired-seed bootstrap intervals. Recovery is undefined for the stable family (no queue-pressure event); therefore its equal-family aggregate is undefined rather than zero. Family recovery counts/times, exhaustion and unfinished-recovery indicators are in the retained outcomes.

| Policy | Work [95% CI] | Completion % [95% CI] | Denial % [95% CI] | Latency [95% CI] | Eligible across all families |
|---|---:|---:|---:|---:|---|
| noop | 209.57 [206.48, 212.49] | 67.79 [67.06, 68.55] | 29.99 [29.29, 30.64] | 13.60 [13.38, 13.84] | no |
| persistent_static | 171.08 [168.56, 173.52] | 81.85 [81.31, 82.43] | 18.15 [17.57, 18.69] | 7.79 [7.54, 8.06] | no |
| resource_aware | 206.40 [203.19, 209.44] | 68.23 [67.47, 69.04] | 29.86 [29.14, 30.55] | 13.21 [12.99, 13.44] | no |
| static | 203.68 [200.55, 206.62] | 70.93 [70.21, 71.72] | 27.52 [26.79, 28.19] | 12.53 [12.29, 12.79] | no |
| threshold | 202.95 [199.90, 205.76] | 71.12 [70.41, 71.89] | 27.19 [26.48, 27.84] | 12.77 [12.56, 12.98] | no |

## Comparisons, ranking and inference

Among eligible arms in stable traffic, all four budgeted rules have zero adversarial work (no attack), so the security objective ties. Noop and threshold avoid unnecessary interventions. In legitimate-burst traffic noop, static and threshold are eligible; their security objective also ties at zero. Resource-aware violates the5% denial threshold there (7.38%).

Every arm is ineligible in low/high exhaustion, shifting and mixed traffic. Thus the strongest safe static baseline and strongest safe adaptive baseline are **unavailable in all four attack families**. Safe-relative effects and a safe10% benefit claim are undefined, not imputed from unsafe comparators.

For transparency only, unsafe raw-work rankings (lowest first) are: low persistent-static,threshold,resource-aware,static,noop; high persistent-static,threshold,static,resource-aware,noop; shifting persistent-static,resource-aware,static,threshold,noop; mixed persistent-static,static,threshold,resource-aware,noop. These rankings are not safety rankings. The full all-pairs paired differences and intervals remain in analysis.json, including null relative effects where reference work is zero. No adaptive rule dominates all families; the resource-aware rule is worse than simpler controls on several outcomes.


Selected unsafe contrasts (full-lifecycle mean work difference, candidate minus static;95% paired intervals):

- high_exhaustion, threshold: -7.80 [-14.10, -2.50], relative reduction 1.87%. Neither arm is eligible.
- mixed, threshold: 1.40 [-5.45, 8.10], relative reduction -0.41%. Neither arm is eligible.
- shifting, resource_aware: -2.45 [-7.65, 2.60], relative reduction 1.01%. Neither arm is eligible.

A. **Controls change outcomes:** yes. For example high-exhaustion noop completion23.67% versus persistent-static62.03%, with work426.90 versus346.30; both fail acceptance.
B. **Sequential consequences:** yes at the modeled mechanism level: controls activate after delay, expire and consume budget; accepted unfinished jobs carry across windows and consume work during later decisions and settlement. Unit cutoff/delay/carryover checks passed, and complete study traces retain those consequences. This is a partially observed sequential simulator, not proof of realistic strategic attacker adaptation or Markov sufficiency.
C. **Useful safe gap beyond strong rules:** not demonstrated. All attack-family arms fail acceptance; diagnostic improvement cannot substitute for an eligible comparison.
D. **Training justified:** NO-GO. Neither a safe10% adaptive benefit nor an acceptable attack-family controller was demonstrated. Do not tune baselines/limits or launch a replacement study from these outcomes.

## Statistical interpretation and limits

Frozen analysis seed20261024;2000 paired whole-workload-seed resamples per family,95% percentile intervals. Policy arms share resampled seed indices; aggregate draws combine independent family strata and average families equally. Safety acceptance uses approved point thresholds with uncertainty reported alongside, not newly imposed confidence-bound thresholds. Operational maxima, not means, determine cap eligibility. Intervals are descriptive across many endpoints and same-data rankings; no multiplicity-adjusted or independent post-selection confirmation is claimed. Feasibility families/seeds are exposed development data and cannot become a reserved final holdout.

Virtual work/latency and synthetic demand are uncalibrated assumptions. Sources overlap legitimate/abusive work; exogenous stochastic shifts are not a measured responsive adversary. Queue-pressure recovery can occur through timeout and is not service health. The four-window historical unit receipt and all old research remain unchanged.

## Next research and training gate

No new training protocol is authorized or justified by this result. The existing [conditional cost-aware DDQN draft](../TRAINING_PREPARATION.md) remains non-executable and NO-GO; its proposed budgets are not inherited from feasibility approval. A future proposal would first need an independently reviewed service/control feasibility argument or calibrated task revision, a new preregistration and owner approval, without retroactively relaxing this study. Only after demonstrating an eligible residual task should cost-aware DDQN, terminal-cost attribution, independent validation/holdout design and explicit training authorization be reconsidered. No additional study was run.

## Exact launch and verification

Executed once from the source checkout with OMP_NUM_THREADS,OPENBLAS_NUM_THREADS,
MKL_NUM_THREADS,VECLIB_MAXIMUM_THREADS all1, PYTHONPATH=rl-defense:shared:standards,
RUN_LIVE_LLM_EVAL=0:
`python -m rl_defense.research.resource.study /private/tmp/ari-resource-feasibility-001-bed44ff2`.
Do not repeat this command as a verification step. Use `verify_study.verify` on
the retained directory with the external index digest above. Dependency versions,
Python build and platform are in the sealed manifest. Source/protocol identity
checks ran before launch and again before completion; a history-preserving merge
is required to retain the execution commit.

## Verification qualification

The same numeric seed IDs are reused across families. The registered aggregate
bootstrap resamples family strata independently; it does not estimate cross-family
shared-seed dependence. Treat aggregate intervals as descriptive under that
assumption, rather than calibrated simultaneous coverage. Per-family point
acceptance failures and the NO-GO conclusion do not depend on aggregate intervals.
The analysis was not rerun or changed after this observation.

`exhausted_ticks` in analysis.json counts the30 decision windows; settlement window
exhaustion/work counters are retained separately in each receipt. Availability,
latency and adversarial-work comparison totals use full-lifecycle outcomes.

The first full software CI run had544 passing tests and one fault-injection fixture
failure: process-lifetime peak RSS inherited from earlier torch tests triggered the
real study guard before the intended injected invalid action. The fixture isolates
that host reading and separately tests memory-limit rejection. The collector,
protocol and sealed study remain unchanged; no formal execution was repeated.
