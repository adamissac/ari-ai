# v8 pre-registration (written and committed before any v8 run)

Written 2026-10-20, after v7 (PR #365, `5deab96`, verdict `reject`). RL stays the defense;
the rule is only a **teacher**, as in v6 and v7. `configs/live/promotion.yaml` is
unchanged. Nothing is promoted: the registry needs a human `usr_*` approver.

**Where v7 stands.** v7 (v6's online DQfD in the platform finding-severity context) closed
ADR-0017's gap on train windows: `noop` in 106/106 quiet windows, a principal block in 94/94
flagged ones. The gate rejected it on one check, `no_per_scenario_regression`. On holdout_v7's
`quiet_week` (rare, small campaigns of 3 requests per window by a customer who is also a
delegate) it scored −3.62 against deployed −3.15 and noop −2.33. holdout_v7 is exposed. Its
numbers are used here only to name the failure mode. No parameter below was chosen from them,
and holdout_v7 is never run again.

## The failure mode, on train data (seen before this pre-registration)

`results/live-retrain-v8/pre_run_evidence.py` (output in `pre_run_evidence.json`) ran v7, v6,
deployed, v7's tuned rules, noop and `always_block_principal` on **train_v8** (14 episodes per
scenario, train seeds) and **val_v4** (8 episodes, val seeds). The platform severity context
was used and no holdout was touched. Return per scenario:

| scenario | v7 | v6 | deployed | rules (v7's) | noop | always_block_principal |
|---|---|---|---|---|---|---|
| train `rare_delegate_runs` (new, 3/window, rare) | **−3.61** | −4.66 | −3.90 | −3.24 | **−3.14** | −2.96 |
| train `trickle_outsider_quiet` (new, 2/window, rare) | −1.18 | −1.83 | −3.64 | −2.58 | −2.71 | −1.53 |
| train_v3 (5 scenarios) | gains of 2.9 to 26 over deployed on each | | | | | |
| val_v4 (4 scenarios) | gains of 8.3 to 12.8 over deployed on each | | | | | |

- On a low-intensity, mostly quiet **train** scenario where the attacker also has legitimate
  traffic, v7 is worse than doing nothing (−3.61 vs −3.14). Its availability is 0.93 against
  noop's 1.00, and it leaves compromise at 0.39. Its margin over deployed (+0.30) is the
  smallest of any train or val scenario. This is quiet_week's pattern, on data v7 never trained on.
- Where blocking costs no legitimate traffic (`trickle_outsider_quiet`, an outsider), v7 is
  fine (−1.18).
- **val_v4 cannot see this regime.** Every val scenario has campaigns of 3 to 6 requests per
  window at p_start ≥ 0.1, and v7 beats deployed by ≥ 8 on each of them.
- train_v3 has no scenario like this either: its rarest campaigns (`delegate_quiet`,
  p_start 0.08) are 6 requests per window by an attacker with little legitimate traffic.

## Hypothesis and the one change

**Hypothesis.** v7 over-blocks in low-intensity, mostly quiet traffic because it never trained
on it. It learned almost everything from demonstrations (val −7.07 at step 0, −7.02 at the
selected 45k), on scenarios where campaigns are frequent and large, so blocking always paid.
Adding that regime to the **train** mix lets the demonstrations and the online TD targets
both carry the cost of blocking a principal with legitimate traffic for a small campaign.
The candidate should then stop trailing doing-nothing there, without losing v7's quiet-window
`noop` behaviour or its flagged-window blocks.

**The change: one thing, the train scenario mix.** `--train-dir train_v8` instead of `train_v3`.
`configs/live/train_v8/` = the five train_v3 scenarios **copied unchanged** (same names, seeds
and config hashes, tested) plus two new low-intensity, mostly quiet ones in the train seed band:
- `rare_delegate_runs` (seeds 8000–8013): carol, a customer and bob's bookkeeper, makes rare
  short runs (p_start 0.06, p_stop 0.45, 3 requests per window) against erin under 7 benign
  per window, while dave reconciles alice's books in bursts.
- `trickle_outsider_quiet` (seeds 8500–8513): mallory, an outsider with rotating tokens, makes
  rare runs of 2 requests per window against alice under 8 benign, while erin reconciles carol's.

The two new scenarios were written after reading v7's report, so they were designed with
quiet_week's description (not its per-episode data) in mind. Their identities, victims,
intensities and probabilities differ from quiet_week's. They are judged by a holdout created
after them (below).

Consequences that follow from the change, not separate changes:
- The expert is still the best train return among the tuned rules and the three block
  baselines, now over seven train scenarios, and the rules are tuned on train_v8.
- Demonstrations are 20 episodes per train scenario (140 episodes). Online episodes still
  cycle round-robin over the train scenarios, so 2/7 of the online steps are low-intensity.
  Training seeds come from the whole train band, as before.

**Everything else is identical to v7.** The loop is v4 (`c_disrupt=1.0`, grant-aware
detector) with `finding_severity_context="platform"`, action space `live_v3`, `OnlineConfig()`
defaults (5000 pretraining updates, 150,000 online steps, ε 0.3→0.05 over 75k, 25%
demonstrations per batch, DQfD λ 1.0, margin 0.8, lr 3e-4, (128, 128), Double DQN, γ 0.99,
target every 1000, buffer 100k), selection on **val_v4 unchanged** (scenario mean, 4 × 8
episodes, every 15k steps plus after pretraining, noop margins {0, 0.1, 0.2, 0.3, 0.5}).
Deployed is the sim-trained policy (30k steps, seed 0), as in every run.

**Not changed, on purpose:** val_v4 and the selection rule. A quiet val scenario or a
regression-aware selection criterion are reasonable next steps, but each would be a second
change. As a result, selection cannot see the low-intensity regime. If v8 fails the per-scenario
check again, that is the first thing to read.

**Code.** `--reference-checkpoint` is repeatable as `NAME=PATH` (`online.parse_references`), so
v6 and v7 are both reported. A single bare path keeps v7's `reference` name and report fields.
`train_v8` is a new directory, and every default is unchanged, so v1–v7 reproduce (their tests
pass unchanged).

## Holdout once, on `configs/live/holdout_v8/` (new for this run)

- `rare_bookkeeper_raids` (seeds 49700–49729): **low-intensity, mostly quiet.** bob, a
  customer and carol's bookkeeper, makes very rare short runs (p_start 0.04, p_stop 0.5,
  3 requests per window) against dave under 8 benign per window.
- `faint_outsider_campaigns` (49800–49829): **low-intensity.** mallory, rotating tokens, reads
  carol's and erin's payments 1 request per window in long faint campaigns (p_start 0.08,
  p_stop 0.15) under 8 benign.
- `insider_pair_windows` (49900–49929): medium. carol and dave (alice's bookkeeper) take turns
  per window reading bob's and erin's payments, 5 per window.

Names and seeds are disjoint from every split, including holdout_v7 and train_v8
(`tests/test_live_v8.py::test_holdout_v8_is_new_and_disjoint_from_everything_else`). 30
episodes each, paired. Policies: deployed, candidate, tuned rules, noop,
always_isolate_payments, the three block baselines (they include the expert) and **two
references, reported only and never in the gate**: `v6` (`results/live-retrain-v6/candidate_online.pt`,
`8113a37f…`, the promoted policy) and `v7` (`results/live-retrain-v7/candidate_online.pt`,
`d1c0c9b5…`).

## The one run

```sh
cd rl-defense
PYTHONPATH=.:../shared:../standards:../examples/payments-lite/target caffeinate -i \
  .venv/bin/python -m rl_defense.live.online --base-steps 30000 --rules-episodes 2 \
  --seed 0 --train-dir train_v8 --val-dir val_v4 --holdout-dir holdout_v8 \
  --severity-context platform \
  --reference-checkpoint v6=results/live-retrain-v6/candidate_online.pt \
  --reference-checkpoint v7=results/live-retrain-v7/candidate_online.pt \
  --out runs/live/retrain-v8 --evidence-dir results/live-retrain-v8
```

Then the evidence pack, and, on **train_v8** windows only, the platform check for v8, v7 and v6:

```sh
.venv/bin/python -m rl_defense.live.evidence pack results/live-retrain-v8 --run "<the command above>"
.venv/bin/python -m rl_defense.live.platform_check \
  results/live-retrain-v8/candidate_online.pt results/live-retrain-v7/candidate_online.pt \
  results/live-retrain-v6/candidate_online.pt --subdir train_v8 \
  --out results/live-retrain-v8/platform_agreement.json
```

## Seen before the run

Unit tests on tiny synthetic scenarios. The v8 smoke test (train_v8 and val_v4 at 1 episode,
a 100-step candidate, the exposed holdout_v2, v6 and v7 as references). The pre-run evidence
above (train_v8 and val_v4 only). The v7 report and provenance, including its holdout_v7
numbers. **No policy was run on holdout_v8.**

## How the result will be read, fixed now

- **The gate decides** (`promotion.yaml`, unchanged), as for v1–v7.
- Reported next to it on holdout_v8: the paired return of candidate − expert, candidate − v7
  and candidate − v6. A paired CI that contains 0 is a tie.
- **The hypothesis is supported on holdout** only if the candidate is not below deployed on
  either low-intensity scenario (`rare_bookkeeper_raids`, `faint_outsider_campaigns`), which
  is the gate's per-scenario rule, and its return there is at least v7's. Otherwise it is not
  supported, whatever the pooled return.
- **Quiet-window behaviour (secondary, not a gate).** The platform check above on train_v8
  windows (7 scenarios × 2 episodes × 10 noop windows per finding case, with real finding
  severities). v8 keeps v7's behaviour only if it recommends `noop` in ≥ 95% of quiet windows
  and a principal block (`block_principal`, `block_principal_long` or `block_top_principal_long`) in ≥ 90% of flagged windows, in both finding cases.
  Lab-vs-platform agreement is reported as measured. It is expected to be 100%, because the
  mapping is equal given the same severities.
- Also reported: v8's return on the train scenario `rare_delegate_runs` against noop (train,
  in-distribution, not held-out).
- Whatever the outcome, no tuning follows on holdout_v8, and the result is reported as is. If
  the gate rejects, v6 stays the promoted policy.
