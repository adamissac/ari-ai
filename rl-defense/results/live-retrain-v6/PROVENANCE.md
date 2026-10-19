# Provenance of the v6 live-training evidence (online DQfD)

How the numbers in [REPORT.md](REPORT.md) were produced, and how to read the verdict.
The method, the budget and the reading rules were fixed beforehand in
[PREREGISTRATION.md](PREREGISTRATION.md).

## Reproduce

The command is the one in PREREGISTRATION.md, run once. The run reports `git_sha`
`c788b5d`, the pre-registration commit, which was pushed before the run. Wall clock:
2026-10-19 09:26 to 10:28 UTC on one CPU.

A first launch at 09:25 failed immediately, before running anything, because the command
was started from the repo root rather than `rl-defense/` and the shell could not open the
log path. No Python ran and no policy saw any scenario. The laptop also slept for part of
the run, which suspends the process without changing it.

Checkpoints and the 156,000-transition experience log are in `runs/` (git-ignored). The
log's SHA-256 is in `candidate.manifest.json` (`lineage.experience_sha256`).

## Order of events

1. `c788b5d` contains the DQfD loss (`DDQNConfig.demo_lambda`, default 0), the online
   trainer `rl_defense/live/online.py`, `holdout_v6` and the pre-registration.
2. Before the run: unit tests, the smoke test (on the exposed holdout_v2), and one timing
   check on a synthetic scenario (PREREGISTRATION.md, "Seen before the run").
3. **No policy was evaluated on holdout_v6 before the final run.** Every holdout_v6
   episode was evaluated once, with nothing re-run or tuned.
4. After the run, the author read only the run's own outputs: the report, the holdout
   episodes, and the action mix of the train-only experience log (below).

## Verdict

**`recommend_promote`.** All seven pre-registered checks pass. This is the first learned
candidate to do so (v1–v5 were rejected).

| | candidate | deployed (sim) | tuned rules (gate bar, and the teacher) |
|---|---|---|---|
| holdout return | **−5.30** [−6.03, −4.58] | −14.81 | −7.58 |
| compromise | 0.185 | 1.000 | 0.374 |
| availability | 0.952 | 1.000 | 0.963 |
| no-attack duty | 0.314 | 0.000 | 0.236 |

- Gain over deployed: **+9.51** [8.17, 10.79], paired over 90 episodes.
- Gain over its own teacher: **+2.28** [1.80, 2.76], paired. The learned policy is
  better than the rules it learned from, on scenarios neither has seen. Under the
  pre-registered reading this is not a tie. Per scenario it beats the teacher on all
  three: −6.32 vs −7.16, −1.25 vs −4.20, and −8.33 vs −11.38. Compromise falls from 0.374
  to 0.185, while availability drops by 0.011.

The recommendation still needs a human `usr_*` approver through
`python -m rl_defense.live.registry promote`. This run did **not** promote anything.

## Caveats that belong next to the verdict

- **A fixed baseline does better on this holdout.** `always_block_principal_long` scores
  −3.89 against the candidate's −5.30. Nearly all of the gap is on `slow_pair`: −4.49 vs
  −8.33, with compromise 0.16 vs 0.44. On the other two scenarios the two are within 0.25.
  That baseline was one of the four expert candidates. On **train** it scored −4.64
  against the rules' −4.31, so the train-only selection chose the rules as teacher. The
  gate's static-rules bar is the tuned rules, as pre-registered.
  The honest claim is: **the learned policy beats the rules it was taught by and the tuned
  rules bar; it does not beat every fixed baseline we report.**
- **Most of the learning happened before the online phase.** Val return after
  demonstration pretraining was −7.05. The best online snapshot, at 105k steps, reached
  −6.98, and the curve stayed between −7.12 and −6.98 for all 150k steps. The holdout gain
  over the teacher therefore comes mainly from pretraining. That means DQfD's large-margin
  imitation plus TD on the demonstrations, which already deviates from the teacher where
  returns say so. The online exploration adds little that val can measure. The step-0
  snapshot was not evaluated on holdout, and won't be now, so this split cannot be
  measured on holdout.
- **The data problem from v4/v5 is fixed.** Blocks are 15% of the demonstrations and 13%
  of the agent's own online experience, against 3–5% in v5:

  | data | noop | block_principal_long | block_principal | block_top_long | monitoring | isolate | rate_limit |
  |---|---|---|---|---|---|---|---|
  | demonstrations | 0.85 | 0.11 | 0.04 | — | — | — | — |
  | online (agent) | 0.48 | 0.07 | 0.04 | 0.02 | 0.13 | 0.08 | 0.09 |

- **One scenario runs a high no-attack duty.** On `customer_turned_attacker` the
  candidate's no-attack duty is 0.675; the rules score 0.522 and the long-block baseline
  0.702. The cap applies overall (0.314, which passes). When an attacker is also a
  customer, blocking it costs its own traffic in later quiet windows, as v4 found.
- **The candidate cannot be served yet.** It is a live_v3 checkpoint, and `PolicyRunner`
  serves only sim and live_v2 checkpoints. Its actions 23 and 24 are not in
  `shared.rl.DefenseActionName`. Serving it needs the long-block contract extension
  (`coordination/messages/20261019T053641Z-…`).
- Lab evidence only (RQ-005): one small demo app, one attack class, and fixture identities.
