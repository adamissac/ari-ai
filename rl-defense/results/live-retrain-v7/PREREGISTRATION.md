# v7 pre-registration (written and committed before any v7 run)

Written 2026-10-19, after contracts 0.14 (PR #364, ADR-0017). RL stays the defense; the
rule is used only as a **teacher**, as in v6. `configs/live/promotion.yaml` is unchanged.
Nothing is promoted: the registry needs a human `usr_*` approver.

**The gap.** ADR-0017 records it. v6 was trained with fixed baseline finding severities on
every node (`loop.DEFAULT_FINDING_SEVERITY`: gateway 0.1, api 0.3, auth 0.2, payments 0.8,
db 0.1). The product derives severities from real findings (`platform_mapping`): 0 on a
node without an open validated finding, otherwise `SEVERITY_SCORE` of the worst one (0.1,
0.25, 0.5, 0.75, 1.0). On platform-producible severities, v6's actions drift. Seen before
this pre-registration, on **train** windows only (`python -m rl_defense.live.platform_check`,
train_v3, 2 episodes × 10 noop windows per scenario):

| v6, train windows | quiet (nothing flagged) | flagged |
|---|---|---|
| no findings (all 0) | `raise_monitoring:gateway` 53/53 | block 30/47, `rate_limit` (auth, gateway) 17/47 |
| validated high BOLA (payments 0.75) | `escalate_to_human` 53/53 | `block_principal` 47/47 |

Lab and platform agree on 100/100 windows per case: the mapping is equal given the same
severities. The problem is the policy's behaviour in a severity regime it never saw, not
the mapping.

**Hypothesis.** Training with finding-severity contexts the platform can actually produce
removes that drift: in quiet windows the policy stops spending actions (noop), and with no
finding on record it still blocks flagged principals instead of rate-limiting whole nodes.
The held-out return should not suffer, since the attack is the same.

**What changes from v6: one thing.** `LoopConfig.finding_severity_context="platform"`
(`rl_defense/live/loop.py`). At every episode reset the loop draws the severities from
`platform_severity_context(seed, 0.5, 0.25)`:
- payments carries the BOLA finding with probability 0.5; gateway, api and auth each carry
  an unrelated finding with probability 0.25;
- a present finding's level is uniform over the five `SEVERITY_SCORE` levels; absent = 0;
- db is always 0, because no payments-lite route maps to it, so the platform cannot give
  it a finding;
- the draw uses its own RNG seeded by the episode seed only, so the traffic is unchanged
  and every policy sees the same context on the same paired episode
  (`tests/test_live_v7.py`).
- About 22% of episodes are fully clean, and 4% hold only the validated high BOLA.
- Reassessment still lowers a node's severity to at most 0.2 when it lands, as in v1–v6.

This applies to **every** loop in the run: rules tuning, expert choice, demonstrations,
online training, val selection and holdout, for every policy. The default stays `"fixed"`,
so v1–v6 reproduce unchanged (`test_default_context_is_the_fixed_v1_to_v6_baseline`; the
v6 tests pass unchanged).

**Method, identical to v6** (`rl_defense/live/online.py`, `OnlineConfig()` defaults, see
results/live-retrain-v6/PREREGISTRATION.md): the expert is the best train return among the
tuned v3 rules and the three fixed block baselines, chosen on train only (2 episodes per
train scenario). 20 demonstration episodes per `train_v3` scenario. Fresh (128, 128) network
in live_v3 dims, 5000 pretraining updates (DQfD λ 1.0, margin 0.8). 150,000 online steps on
`train_v3`, train-band seeds, ε 0.3→0.05 over 75k, batch 64 with 25% demonstrations, lr 3e-4,
Double DQN, γ 0.99, hard target every 1000, buffer 100k. Selection on `val_v4` every 15k
steps plus after pretraining, scenario-mean over 4 × 8 episodes, noop margins
{0, 0.1, 0.2, 0.3, 0.5}. The v4 loop (`c_disrupt=1.0`, grant-aware detector), action space
live_v3. Deployed = the sim-trained policy (30k steps, seed 0), as in every run.

**Holdout once** on `configs/live/holdout_v7/`, new for this run: `quiet_week` (rare short
campaigns by a customer who is also a delegate; mostly quiet windows), `bookkeeper_and_outsider`
(a delegate and a token-rotating outsider alternating per request), `steady_trickle`
(always-on, 2 attack requests per window under 9 benign). Seeds 40500, 41500, 42500, 30
episodes each. Names and seeds are disjoint from every split
(`test_holdout_v7_is_new_and_disjoint_from_everything_else`). Policies: deployed (sim),
candidate, tuned rules, noop, always_isolate_payments, the three block baselines (they
include the expert), and **reference = the promoted v6 checkpoint**
(`results/live-retrain-v6/candidate_online.pt`, `8113a37f…`), reported only and never part
of the gate.

**The one run:**

```sh
cd rl-defense
PYTHONPATH=.:../shared:../standards:../examples/payments-lite/target \
  .venv/bin/python -m rl_defense.live.online --base-steps 30000 --rules-episodes 2 \
  --seed 0 --train-dir train_v3 --val-dir val_v4 --holdout-dir holdout_v7 \
  --severity-context platform \
  --reference-checkpoint results/live-retrain-v6/candidate_online.pt \
  --out runs/live/retrain-v7 --evidence-dir results/live-retrain-v7
```

Then, on **train** windows only, the platform check for both policies:

```sh
.venv/bin/python -m rl_defense.live.platform_check \
  results/live-retrain-v7/candidate_online.pt results/live-retrain-v6/candidate_online.pt \
  --out results/live-retrain-v7/platform_agreement.json
```

**Seen before the run.** Unit tests on tiny synthetic scenarios. The v7 smoke test (train_v3
and val_v4 at 1 episode, a 100-step candidate, the exposed holdout_v2, v6 as reference).
The v6 platform check above, on train windows. No policy was run on holdout_v7.

**How the result will be read, fixed now:**
- The gate decides (`promotion.yaml`, unchanged), as for v1–v6.
- Reported next to it: the paired return of candidate − expert, and of candidate − v6
  reference, on holdout_v7. A candidate that only ties v6 here is a tie.
- Secondary, not a gate: the platform check. (a) Lab-vs-platform agreement for v7 on quiet
  and flagged windows, with real finding severities. It is expected to be 100% because the
  mapping is equal, and it is reported as measured. (b) The share of quiet windows in which
  v7 recommends `noop`, against v6's 0/106 above. The hypothesis is supported only if v7's
  share is clearly higher and its flagged windows still recommend a principal block.
- Whatever the outcome, no tuning follows on holdout_v7, and the result is reported as is.
  If the gate rejects, v6 stays the promoted policy, and the gap stays open in ADR-0017.
