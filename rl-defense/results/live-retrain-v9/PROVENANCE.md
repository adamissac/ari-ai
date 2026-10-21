# V9 five-seed lab study

The preregistered hypothesis is **not supported**. No policy was promoted.

Candidate-minus-incumbent return: -0.0458, 95% training-seed bootstrap CI [-0.1758, 0.0843]. Five seeds, 100 paired episodes per scenario.

See study_summary.json for every policy, metric and per-scenario seed value; study_verdict.json for every gate; platform_agreement.json for train-only mapping checks; failure_case.json for the worst episode and raw trajectories.

RUN.json records source, preregistration, registry hashes and hardware. Each seed contains exact checkpoint/experience/evaluation evidence. Small-n paired t tests assume independent training seeds; bootstrap intervals with n=5 have limited precision. The fixed incumbent/reference policies do not have fresh training-seed uncertainty.

Measured in the owned, in-process payments-lite lab. These results do not establish real-world effectiveness and are not the DefenseSimEnv-v0 benchmark.

## Completed experiment and tradeoffs

All five fixed seeds completed from frozen learning source `29aa5f8ae3b2878ee7d95e22f0052ced7b3afca3`. Wall time was 3h 7m 12s (2026-10-20 22:47:27 UTC to 2026-10-21 01:54:39 UTC), with five concurrent CPU workers. Each consumed 4,200 demonstration transitions, 5,000 pretraining updates and 150,000 online transitions / 150,000 online updates. Held-out evaluation retained 11 policies × 3 scenarios × 100 episodes × 5 training seeds = 16,500 episodes, each 30 windows. No held-out evaluation was repeated during reporting.

The primary hypothesis is unsupported even though both quiet-scenario mean returns exceed the fixed v8 reference. Overall candidate return is −5.7016 versus v6 −5.6559; paired mean gain −0.0458 (95% training-seed bootstrap interval −0.1758 to +0.0843; two-sided paired t / Holm p=0.5688). Every seed fails both the return-confidence and no-scenario-regression checks; each passes the other five checks. No best seed is chosen.

Compromised attack-request fraction falls from 27.29% to 21.06%, but benign-request availability falls from 91.69% to 89.92%. Quiet benign-request disruption rises from 5.86% to 7.55%, quiet-window disruptive-control duty from 19.47% to 23.53%, while non-noop actions/window fall from 0.630 to 0.081. These are the lab's request/window metrics, not simulator impact or time-to-compromise measurements. All six metrics, bootstrap intervals, paired tests and Holm corrections are retained in `study_summary.json`.

Scenario mean returns (candidate / v6 / v8): faint outsider −1.8465 / −1.8566 / −2.4500; quiet rogue −2.1825 / −2.4013 / −2.1837; mixed delegate rotation −13.0758 / −12.7097 / −12.9717. The mixed scenario regresses against both references. The tiny quiet-rogue improvement over v8 is only the preregistered mean comparison; it does not establish a statistically reliable improvement. Fixed v6/v7/v8 checkpoints have no fresh retraining uncertainty, so this study is not a pure causal ablation against five newly trained v8 controls.

## Selection and failure evidence

Selected online steps for seeds 0–4 are 105,000, 150,000, 75,000, 120,000 and 0, with noop margins 0, 0, 0, 0.2 and 0.2. Seed4 selects its demonstration-pretrained snapshot (5,000 optimizer updates); its full 150,000-step experiment remains saved. Selected lineage hashes describe only experience available at selection, while complete experiment hashes retain all 154,200 rows/seed. `checkpoint_verification.json` records verified embedded manifests, sidecars, source, optimizer counts and digest identity.

The worst paired episode is training seed0, faint_outsider_reconciliation evaluation seed40783. Candidate return −23.02 versus v6 −1.58: 23/23 attack requests compromise versus 1/23, with zero benign requests blocked in either run. The saved candidate trace blocks cus_mallory once then takes noop for 29 windows, missing the later attack; v6 uses persistent principal blocks and additional controls after the first compromised read. `failure_case.json` preserves both complete 30-window traces with observations, masks, actions, outcomes and reward components. This is observed behavior, not proof of an underlying learned causal mechanism.

Train-only platform diagnostics use two fixed finding cases and 280 windows/model. Behavior thresholds (quiet noop ≥95%, flagged principal block ≥90%) are reported separately from mapping agreement in `study_verdict.json`; neither substitutes for held-out promotion evidence. All five models pass both behavior thresholds in both cases, with 100% mapping agreement (1,400/1,400 windows overall); this train-only success coexists with the held-out failures.

## Provenance and registry

The actual incumbent v6 checkpoint is `8113a37f4ff9360a9efed2e9f499c4b2ae36e97bfb78372436f97da106fc05f1`. The captured registry digest matches launch and remains unchanged; no registration, approval or promotion was performed. Historical v8 `recommend_promote` used a fresh simulator baseline and cannot authorize replacement of v6.

Reporting helpers were integrated only after all jobs exited successfully (commits `635c2c1`, `44a5172`); hardened aggregation produces exactly the same serialized statistics as frozen-source aggregation. `environment.json`, `registry_snapshot.json`, `observed_progress.json`, exact per-seed commands/logs and `RUN.json` retain execution provenance. Observed progress is a partial polling record; complete validation histories are in every checkpoint manifest. Optional plotting ran in an isolated dependency directory and did not change the training runtime. `STUDY_EVIDENCE.json` pins the final stored bundle; read-only verification is documented in `POSTPROCESSING.md`.

Next research should address the mixed-rotation regression and missed persistent attacks, with a new preregistered split before any retraining. This holdout is now exposed and must not become a tuning set while still being called fresh. v6 remains deployed and ADR-0017's product behavior gap remains open.
