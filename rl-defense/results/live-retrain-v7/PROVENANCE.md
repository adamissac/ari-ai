# Provenance of the v7 live-training evidence (online DQfD, platform finding severities)

How the numbers in [REPORT.md](REPORT.md) and [platform_agreement.json](platform_agreement.json)
were produced, and how to read them. The method, the budget and the reading rules were fixed
beforehand in [PREREGISTRATION.md](PREREGISTRATION.md).

## Reproduce

The commands are the two in PREREGISTRATION.md, each run once. Wall clock: 2026-10-19
23:07 to 2026-10-20 00:20 UTC on one CPU (macOS, `caffeinate -i`, so no sleep this time).
A full `pytest` of rl-defense ran on the same machine at the same time. That only
affects wall clock, since all randomness is seeded.

**git_sha.** The run started from `4b537d2`, the pre-registration commit, which was pushed
before the run. The report's `git_sha` field says `cafbf0b`, because `online.run` reads
`HEAD` when it writes the report, at the end. `cafbf0b` was committed while the run was in
progress, and it changes only `rl_defense/live/evidence.py` (the `pack` command) and
`tests/test_live_v7.py`. The run's process does not import `evidence.py`, and Python had
already loaded every module it uses from `4b537d2`. No file the run executes differs
between the two commits (`git diff --stat 4b537d2 cafbf0b`).

**Evidence.** `python -m rl_defense.live.evidence pack results/live-retrain-v7` built
`EVIDENCE.json`:
- the checkpoint `candidate_online.pt` (`d1c0c9b5…`), stored as is;
- the complete 153,000-line log (3,000 demonstrations + 150,000 online), stored gzip as
  `candidate_online_experience.jsonl.gz` (uncompressed `86f0d9a0…`, which is
  `online.experiment.experience_sha256` in the manifest);
- the selected snapshot's 48,000-line prefix (`d249d20f…`), which the checkpoint's own
  `lineage.experience_sha256` pins. It is derived from the log, never stored twice.

`pack` checked every digest against the report before it removed the uncompressed files.
`python -m rl_defense.live.evidence verify|restore results/live-retrain-v7` checks or
rebuilds them, and `tests/test_v7_evidence.py` does both in CI. Unlike v6, the lineage
counts only the selected prefix (48,000 = 3,000 + 45,000), and no update was skipped.

## Order of events

1. `4b537d2`: the severity context (`LoopConfig.finding_severity_context`), `--severity-context`
   and `--reference-checkpoint` in `online.py`, `platform_check.py`, `holdout_v7` and the
   pre-registration. Pushed.
2. Before the run: unit tests, the v7 smoke test on the exposed holdout_v2, and the v6
   platform check on train windows (PREREGISTRATION.md, "Seen before the run").
3. **No policy was evaluated on holdout_v7 before the final run.** Every holdout_v7 episode
   was evaluated once, with nothing re-run or tuned.
4. After the run: the platform check for v7 and v6 on train windows, once. Then the author
   read the run's outputs.

## Verdict

**`reject`.** Six of the seven pre-registered checks pass. `no_per_scenario_regression` fails:
on `quiet_week` the candidate returns −3.62 against the deployed policy's −3.15 (−0.47).
v6 stays the promoted policy. Nothing was promoted.

| holdout_v7 | candidate (v7) | reference (v6) | deployed (sim) | tuned rules (teacher) | noop |
|---|---|---|---|---|---|
| return | **−5.38** [−6.10, −4.62] | −5.55 | −15.26 | −11.11 | −14.40 |
| compromise | 0.122 | 0.166 | 1.000 | 0.472 | 1.000 |
| availability | 0.882 | 0.897 | 0.992 | 0.923 | 1.000 |
| no-attack duty | 0.382 | 0.306 | 0.024 | 0.264 | 0.000 |
| actions / step | **0.11** | 0.64 | 0.70 | 0.06 | 0.00 |

- Gain over deployed: +9.88 [7.24, 12.62]. Gain over its teacher: +5.73 [3.68, 7.76].
- **Against v6: +0.17 [−0.14, 0.47], a tie** under the pre-registered reading. v7 is not
  better than v6 on held-out return.
- Per scenario (candidate / v6 / deployed): bookkeeper_and_outsider −9.27 / −9.24 / −11.74;
  quiet_week −3.62 / −4.12 / −3.15; steady_trickle −3.26 / −3.30 / −30.88.

## Why `quiet_week` fails, and what that does and does not mean

`quiet_week` is mostly quiet. Its campaigns are rare, short and small (3 requests per window),
so doing nothing is cheap: noop scores −2.33 and the deployed policy −3.15. Any policy that
blocks pays for disruption: the candidate's availability there is 0.94, and its no-attack
duty is 0.235. The candidate cuts compromise from 1.00 to 0.49, which is not enough to make
up for it. v6 would fail the same check by more (−4.12), and so would every block baseline
except `always_block_principal` (−2.74). The gate's per-scenario rule is strict by design
and was not changed. This is a real loss to the deployed policy on that scenario, not a
measurement artefact.

## The training-distribution gap (secondary, not a gate)

The platform check ran on train_v3 windows: 5 scenarios × 2 episodes × 10 noop windows, for
each of two finding sets the product can hold. Lab facts used the platform's severities.
Platform facts came from `platform_mapping` plus the reporter's `RouteDetection` counters.

| train windows | v7 quiet (53) | v7 flagged (47) | v6 quiet (53) | v6 flagged (47) |
|---|---|---|---|---|
| no findings | noop 53 | block_principal 47 | raise_monitoring:gateway 53 | block 30, rate_limit 17 |
| validated high BOLA | noop 53 | block_principal 47 | escalate_to_human 53 | block_principal 47 |

- **Lab vs platform agreement: 200/200 for v7** (100% on quiet and on flagged windows, both
  cases). v6 also scores 200/200. Agreement measures the mapping, which is equal given the
  same severities. It does not measure whether the policy's choices make sense.
- **The pre-registered hypothesis is supported on these windows.** v7 recommends `noop` in
  106/106 quiet windows, against v6's 0/106. It recommends a principal block in 94/94
  flagged windows, including with no finding on record, where v6 rate-limited whole nodes
  in 17/47. On holdout this shows as 0.11 actions per step against v6's 0.64 at equal return.
- These are train windows under noop, so they are not held-out. They also cover two
  finding sets, not every set the product can hold.

## Caveats that belong next to the verdict

- **Selection stopped early again.** Val peaked at −7.02 between 30k and 60k steps and then
  drifted down to −7.27 at 150k. The selected snapshot is at 45k with noop margin 0.2. As
  in v6, almost all of the return comes from demonstration pretraining (val −7.07 at step 0).
- **A fixed baseline does better on this holdout.** `always_block_principal` scores −4.49
  against −5.38. It was an expert candidate, but on train it scored −6.09, so the
  train-only selection did not choose it.
- No tuning follows on holdout_v7. A later run needs a new holdout.
