# Provenance of the v5 live-retraining evidence (CQL)

How the numbers in [REPORT.md](REPORT.md) were produced, and how to read the verdict.
The hypothesis, the single change and the reading rules were fixed beforehand in
[PREREGISTRATION.md](PREREGISTRATION.md).

## Reproduce

The command is the one in PREREGISTRATION.md, run once. It is identical to v4 except for
`--holdout-dir holdout_v5 --cql-alpha 1.0`. The run reports `git_sha` `687629d`, the
pre-registration commit, which was pushed before the run. Wall clock: 2026-10-19 07:54 to
08:48 UTC on one CPU. Checkpoints and raw datasets are in `runs/` (git-ignored), and their
SHA-256 digests are in the manifests here.

## Order of events

1. `687629d` contains CQL (`DDQNConfig.cql_alpha`, default 0), `holdout_v5`, and the
   pre-registration. Before it, only unit tests ran. The v5 pipeline smoke test uses the
   exposed `holdout_v2`.
2. **No policy was evaluated on holdout_v5 before the final run.** Every holdout_v5
   episode was evaluated once, with nothing re-run or tuned.
3. After the run, the author read the run's own outputs: the report, the candidate
   manifest, and the action mix of the three **train** experience datasets (below). No
   further episodes were run.

## Verdict

**`reject`**. Six of seven checks pass. The candidate is very cautious: availability is
0.991, false disruption 0.010, and no-attack duty 0.045. It fails `beats_static_rules`:
−12.17 against the tuned rules' −7.41. Its compromise rate is 0.675. It beats the deployed
policy by +3.57 [2.47, 4.75].

## Reading the pre-registered questions

- **Did CQL fix the degradation? Yes, by both pre-registered tests.** The selected
  snapshots are at updates 6000, 10000 and 12000; v4 picked 2000 in every round. The
  round-2 val return at 16000 updates is −15.31, within 1.0 of its best (−14.81). In v4 it
  fell from −5.61 to −15.28. The CQL gap (logsumexp − Q(data action)) falls steadily from
  2.35 to 1.53 over training.
- **Did that produce a better policy? No.** Training is now stable, but stable near the
  data: val return improves only from −15.85 (warm start) to about −14.3. v4 reached
  −5.6 on the same val set.
- **Does it beat `always_block_principal`? No:** −12.17 against −4.79. The
  pre-registration says this ends the learned-policy track on this app.

## Why CQL was too conservative here (from the train datasets only)

CQL keeps Q close to the actions the dataset contains. Block actions, the only controls
that contain this attack without blocking whole nodes, make up just 3–5% of the
experience:

| Round | raise_monitoring | request_reassessment | noop | isolate | rate_limit | any block |
|---|---|---|---|---|---|---|
| 1 | 0.37 | 0.20 | 0.09 | 0.13 | 0.13 | 0.029 |
| 2 | 0.38 | 0.17 | 0.15 | 0.11 | 0.10 | 0.038 |
| 3 | 0.33 | 0.15 | 0.25 | 0.08 | 0.08 | 0.052 |

The behavior policy is the sim-trained policy plus ε-greedy exploration, and that policy
favours monitoring and reassessment. So the data covers the useless actions densely and
the useful ones thinly. The likely reading of v4, not verified here, is that plain DDQN
overestimated the rare actions and degraded with more updates. CQL with α = 1.0 suppresses them, so the candidate rarely blocks (compromise
0.675). This is offline RL's known coverage limit: it cannot do much better than the
behavior data supports. A smaller α would sit between the two failure modes, but tuning α
after seeing this would break the pre-registration, so it was not done.

## What this means

Across five pre-registered runs, every learned candidate was rejected. With the
grant-aware detector, a fixed `always_block_principal` policy beats every candidate on
holdout return (v4: −7.31 vs −7.85; v5: −4.79 vs −12.17). It also clears every metric bar
of `promotion.yaml` on both holdouts. On this app, the defense that worked came from fixing
the instrumentation, not from learning. The learned-policy track on payments-lite is closed,
as agreed before this run. Lab evidence only (RQ-005). Nothing was promoted.
