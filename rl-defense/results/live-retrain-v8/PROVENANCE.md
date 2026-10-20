# Provenance of the v8 live-training evidence (v7 method, low-intensity train mix)

How the numbers in [REPORT.md](REPORT.md), [platform_agreement.json](platform_agreement.json)
and [post_run_train_check.json](post_run_train_check.json) were produced, and how to read
them. The method, the budget and the reading rules were fixed beforehand in
[PREREGISTRATION.md](PREREGISTRATION.md).

## Reproduce

The run command is the one in PREREGISTRATION.md, run once. Wall clock: 2026-10-20 00:55 to
02:24 UTC on one CPU (macOS, `caffeinate -i`). A full rl `pytest` ran on the same machine
during the first minutes, which only affects wall clock (all randomness is seeded). The
report's `git_sha` is `15e25f9`, the pre-registration commit, pushed before the run. Nothing
was committed while the run was in progress.

**Deployed checkpoint digest.** The sim-trained deployed policy is retrained in every run
(30k steps, seed 0). Its file digest (`cea15d7c…`) differs from v7's (`426b187b…`) because
the checkpoint embeds `created_at`. The weights are seeded. Every policy in this report was
evaluated in this one run.

**Evidence.** `python -m rl_defense.live.evidence pack results/live-retrain-v8` built
`EVIDENCE.json`, in v7's format:
- the checkpoint `candidate_online.pt` (`ec8b5042…`), stored as is;
- the complete 154,200-line log (4,200 demonstrations + 150,000 online), stored gzip as
  `candidate_online_experience.jsonl.gz` (uncompressed `c2789ebb…`);
- the selected snapshot's 109,200-line prefix (`55f17bfc…`), which the checkpoint's
  `lineage.experience_sha256` pins. It is derived from the log, never stored twice.

`python -m rl_defense.live.evidence verify|restore results/live-retrain-v8` checks or rebuilds
them, and `tests/test_v8_evidence.py` does both in CI.

## Order of events

1. `15e25f9`: `configs/live/train_v8/`, `configs/live/holdout_v8/`, repeatable
   `--reference-checkpoint NAME=PATH`, the pre-run evidence (train_v8 and val_v4 only) and
   the pre-registration. Pushed.
2. The run, once. **No policy was evaluated on holdout_v8 before it**, and every holdout_v8
   episode was evaluated once.
3. After the run, each once: the evidence pack; the platform check for v8, v7 and v6 on
   train_v8 windows; v8 on the train_v8 scenarios (`post_run_train_check.py`). Then the
   author read the outputs.

## Verdict

**The gate returns `recommend_promote`: all seven pre-registered checks pass.** Nothing
was promoted. Promotion needs a human `usr_*` approver, and the reading below matters for that
decision.

| holdout_v8 | candidate (v8) | v7 (ref.) | v6 (ref., promoted) | deployed (sim) | tuned rules (teacher) | noop |
|---|---|---|---|---|---|---|
| return | −5.86 [−6.89, −4.81] | **−5.40** | −5.94 | −10.33 | −6.46 | −9.22 |
| compromise | 0.345 | 0.436 | 0.394 | 1.000 | 0.308 | 1.000 |
| availability | 0.917 | 0.932 | 0.929 | 0.984 | 0.911 | 1.000 |
| actions / step | 0.12 | 0.11 | 0.75 | 0.64 | 0.11 | 0.00 |

- Gain over deployed: +4.47 [3.14, 5.81]. Over its teacher: +0.60 [0.08, 1.17].
- **Against v6: +0.08 [−0.40, 0.50], a tie.**
- **Against v7: −0.46 [−0.96, −0.07]. v8 is worse than v7** on this holdout.
- `always_block_principal_long` (a fixed baseline, not chosen as expert on train) scores
  −5.16, better than the candidate, as in v6 and v7.

Per scenario (return):

| holdout_v8 | v8 | v7 | v6 | deployed | noop |
|---|---|---|---|---|---|
| `rare_bookkeeper_raids` (low-intensity, mostly quiet) | −3.03 | **−2.87** | −3.70 | −3.55 | −2.50 |
| `faint_outsider_campaigns` (low-intensity) | −2.83 | **−1.26** | −2.05 | −13.17 | −12.03 |
| `insider_pair_windows` (medium) | −11.71 | −12.05 | −12.08 | −14.29 | −13.13 |

## Reading, as pre-registered

- **Gate:** passes. `no_per_scenario_regression` passes with a smallest margin of +0.51 on
  `rare_bookkeeper_raids`.
- **Hypothesis: not supported.** The rule was "not below deployed on either low-intensity
  scenario *and* at least v7's return there". The first half holds. The second fails on both:
  −3.03 vs v7 −2.87 and −2.83 vs v7 −1.26.
- **Quiet-window behaviour: kept.** The platform check ran on train_v8 windows: 7 scenarios ×
  2 episodes × 10 noop windows per finding case, with real finding severities. v8 recommends
  `noop` in 178/178 quiet windows and `block_principal` in 102/102 flagged ones, in both finding
  cases, which clears the ≥95% and ≥90% thresholds. Lab-vs-platform agreement is 280/280. v7 is
  identical (178/178 noop, 102/102 block, 280/280). v6 again shows ADR-0017's drift:
  `raise_monitoring:gateway` or `escalate_to_human` in every quiet window, and with no finding
  on record it blocks in only 34/51 flagged windows (it rate-limits nodes in the other 17).
  Agreement measures the mapping, not the policy.
- **Train `rare_delegate_runs` vs noop (in-distribution, not held-out):** v8 −4.01, noop −3.14,
  v7 −3.61 (pre-run table). **v8 trails doing nothing on a low-intensity scenario it trained
  on**, by more than v7 did. The change did not teach the trade-off it was meant to teach.

## What this means

1. **The gate passing is not evidence that the train-mix change worked.** holdout_v8 is an
   easier holdout for the per-scenario rule than holdout_v7. On its low-intensity, mostly quiet
   scenario, deployed trails noop by 1.05 (quiet_week: 0.82). On every holdout_v8 scenario v7's
   numbers also clear deployed, and v7 beats the tuned rules overall (−5.40 vs −6.46). This is
   read from the report and was not pre-registered for v7. v7 was not re-gated, and it must not
   be promoted on holdout_v8 numbers chosen after the fact.
2. **Against the promoted v6, v8 ties on return** and differs in behaviour: 0.12 against 0.75
   actions per step, and on train windows with real finding severities it recommends `noop`
   where v6 escalates or raises monitoring. That is the ADR-0017 gap, and v8 is the first
   candidate that both shows the fixed behaviour and passes the gate.
3. **Online learning moved for the first time, but selection is still blind to the target
   regime.** Val went from −7.03 after pretraining to −6.74 at 105k steps (v7: flat at −7.02).
   The selected snapshot used noop margin 0.0. val_v4 has no low-intensity scenario. The val
   gain came on the regular scenarios (val3_mixed −6.93 vs v7 −8.04), while low-intensity
   behaviour got worse (train `rare_delegate_runs`, holdout_v8's two low-intensity scenarios).
   A val set with a quiet scenario, or a selection that penalises per-scenario losses against
   noop or deployed, is the next single change to try. It needs a fresh holdout.

No tuning follows on holdout_v8. Its numbers are now exposed.
