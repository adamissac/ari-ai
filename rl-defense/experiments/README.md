# RL experiments log

Goal: improve on the protocol-v0 DDQN (held-out pooled return −65.6 [−72.1, −59.7],
compromise 47.5%, false disruption 53.9%, uptime 93.8%). We want better return **and**
lower false disruption **without** raising compromise or db loss.

## Selection protocol (docs/17 compliant)

| Item | Value |
|---|---|
| Configs used for selection | `configs/train/*.yaml` only |
| Validation training seeds | 10, 11, 12 (final seeds 0–4 are never used for selection) |
| Validation episode seeds | 2000–2099, 100 per training config |
| Held-out `configs/eval/` + eval seeds 1000–1099 | used **once**, for the single final candidate |
| Environment | `DefenseSimEnv-v0`, reward coefficients unchanged |
| Ranking | validation mean return; worst-seed return, db-loss rate, false disruption and per-node impact reported alongside |

Run a round with `python -m experiments.select --round <name> configs/ddqn/<candidates>.yaml`.
Each round writes `experiments/results/<round>.md` (table) and `<round>.json` (per seed and
per config). Candidate configs (DDQNConfig overrides plus `steps`) live in `configs/ddqn/`.

The coordinator's failure analysis of v0 (held-out, so used only to choose what to try, never
for selection) found that DDQN loses the db in 9.8% of episodes versus 0.3% for the threshold
rules, with the worst episodes in fast, aggressive scenarios. Validation tables therefore
also report db loss and per-node impact.

## Rounds

### Round 1 — algorithm and training-length sweep ([table](results/r1.md))

10 candidates × 3 validation seeds, nominal training configs only.

| Candidate | Steps | Validation return (mean ± std) | Worst seed | db loss % | False disruption % |
|---|---|---|---|---|---|
| **lr3e4_500k** (lr 3e-4) | 500k | **−42.5 ± 15.4** | −59.8 | 4.8 | 53.9 |
| ablation_vanilla_dqn_200k | 200k | −73.1 ± 10.3 | −79.5 | 12.7 | 50.7 |
| v0_baseline (v0 defaults) | 200k | −91.8 ± 49.8 | −149.1 | 8.6 | 59.6 |
| nstep3_500k | 500k | −92.5 ± 52.5 | −151.5 | 8.8 | 40.3 |
| dueling_500k | 500k | −130.3 ± 41.7 | −159.3 | 25.4 | 46.5 |
| batch128 / long500k / long1m / wide256 / soft (all lr 1e-3) | 500k–1M | −168 to −192 | −197 to −247 | 25–44 | 42–57 |

Findings:
- **Learning rate is the main lever.** At the v0 learning rate (1e-3), training longer makes
  things *worse*: the training logs show these runs reach about −38 mid-training, then
  oscillate as Q-value estimates drift (q_mean swinging between −44 and +12, loss rising to
  2–4). The final checkpoint is a lottery. At lr 3e-4, Q-values stay stable around −13 and
  the loss falls to 0.1–0.3.
- v0 itself has large seed variance on validation (one seed at −149), matching the held-out
  seed spread the coordinator reported.
- The vanilla-DQN ablation was *not* worse than Double DQN at 200k steps on validation
  (−73 vs −92, within noise given v0's ±50). We report it as found; Double DQN stays the
  default because the round-2 winner uses it and the ablation is a single setting.
- n-step returns lowered false disruption (40%) but did not help return at lr 1e-3.

Decision: carry lr 3e-4 forward and test robustness (round 2).

### Round 2 — robustness to attacker speed ([table](results/r2.md))

Motivation: the coordinator's held-out stress test of v0 (evaluation-only, seeds 3000–3049,
not used for selection) showed DDQN's lead over the threshold rules vanishing as attackers
speed up, with db loss climbing to 61% at ×2.5 (rules: 10%). Round 2 adds training-time
domain randomization (`adversary_scale: [0.5, 2.5]`) and validates every candidate on the
training configs at factors ×0.5, ×1, ×1.5, ×2, ×2.5.

**Selection rule (written before seeing round-2 results):**
1. Rank by robust validation return (mean over the five factors, mean over seeds 10–12).
2. Among candidates within one standard deviation of the leader, prefer the lower robust
   db-loss rate.
3. The pick must not be worse than `r2_v0_ref` at ×1.0 (no nominal regression).
4. That single candidate is then trained on seeds 0–4 and evaluated once on the held-out
   configs, plus the held-out stress test.

Round-2 results (robust return = mean over ×0.5…×2.5; db loss at ×1 / averaged over factors):

| Candidate | Robust return | Worst seed | ×1 | ×2.5 | db loss ×1 / robust % | Compromise ×1 % | False disruption ×1 % |
|---|---|---|---|---|---|---|---|
| **r2_lr3e4_1m_dr** | **−56.9 ± 33.4** | −95.5 | −31.3 | −106.8 | 1.0 / 7.3 | 20.0 ± 29.5 | 57.5 |
| r2_lr3e4_500k_dr_nstep3 | −60.9 ± 29.1 | −93.7 | −36.5 | −107.5 | 3.0 / 8.5 | 25.6 | 53.4 |
| r2_lr3e4_500k_dr | −62.1 ± 19.4 | −78.6 | −30.0 | −122.9 | 2.8 / 11.9 | 18.1 | 64.3 |
| r2_lr1e4_500k_dr | −67.2 ± 46.8 | −121.1 | −34.5 | −131.6 | 5.3 / 14.9 | 12.3 | 69.4 |
| r2_lr3e4_500k_dr_wide256 | −89.9 ± 12.5 | −104.3 | −42.4 | −181.5 | 2.7 / 13.8 | 27.9 | 55.4 |
| r2_lr3e4_500k (no DR) | −94.6 ± 41.9 | −140.3 | −42.5 | −188.2 | 4.8 / 20.5 | 33.1 | 53.9 |
| r2_lr3e4_500k_dr_dueling | −103.0 ± 51.7 | −159.4 | −56.9 | −192.4 | 7.0 / 19.0 | 36.8 | 51.2 |
| r2_v0_ref (v0 defaults) | −158.5 ± 48.3 | −211.0 | −91.8 | −285.4 | 8.6 / 25.3 | 56.3 | 59.6 |

Applying the rule: `r2_lr3e4_1m_dr` leads; four candidates are within one std, and it has the
lowest robust db loss among them; its ×1 return beats v0's. **Domain randomization is the
second big lever**: at the same lr and length, DR raises the ×2.5 return from −188 to −123
and cuts robust db loss from 20.5% to 11.9%.

The problem left is **seed instability**: for the winner, seeds 11 and 12 reach a robust
−37.6 while seed 10 gets −95.5 (54% compromise at ×1). With 3 seeds that also makes the
selection itself noisy. So before using the final seeds, round 3 targets variance.

### Round 3 — seed stability ([table](results/r3.md))

Candidates, all at lr 3e-4, 1M steps, DR ×0.5–2.5: the round-2 winner (reference);
in-training checkpoint selection (`select_every: 50000` from 300k steps, scored on training
configs at ×1 and ×2 with episode seeds 5000–5029, disjoint from every other seed range);
linear lr decay to 3e-5; both together; and n-step 3 with checkpoint selection.

**Selection rule (written before seeing round-3 results):** same as round 2, on **5**
validation seeds (10–14): highest robust return; within one std of the leader prefer lower
robust db loss; must beat `r2_v0_ref` at ×1. The winner goes to the final held-out run.

Round-3 results (5 validation seeds; robust = mean over ×0.5…×2.5):

| Candidate | Robust return | Robust per seed | ×1 | ×2.5 | db loss ×1 / robust % | Compromise ×1 % | False disruption ×1 % | Uptime ×1 % |
|---|---|---|---|---|---|---|---|---|
| **r3_1m_dr_nstep3_sel** | **−32.8 ± 5.2** | −32.6, −27.3, −41.4, −31.1, −31.6 | −22.5 | −51.9 | 0.0 / 1.8 | 4.5 | 75.8 | 96.0 |
| r3_1m_dr_lrdecay_sel | −33.6 ± 2.4 | −31.1, −32.0, −32.6, −35.5, −36.8 | −22.4 | −57.2 | 0.4 / 3.1 | 4.2 | 74.9 | 97.0 |
| r3_1m_dr_sel | −38.1 ± 2.8 | −40.8, −37.6, −41.1, −36.3, −34.5 | −23.1 | −68.5 | 1.0 / 5.3 | 3.9 | 72.2 | 96.3 |
| r3_1m_dr (round-2 winner) | −55.1 ± 23.8 | −95.5, −37.6, −37.6, −55.6, −49.3 | −29.4 | −107.1 | 1.0 / 7.4 | 15.1 | 62.8 | 94.8 |
| r3_1m_dr_lrdecay | −55.4 ± 14.2 | −53.3, −38.9, −56.7, −77.9, −50.1 | −29.3 | −106.7 | 3.1 / 11.9 | 13.8 | 55.7 | 95.5 |

Findings:
- **In-training checkpoint selection is the third lever.** It fixes the seed instability:
  std drops from 23.8 to 2.4–5.2 and the worst seed improves from −95.5 to −41.4. The
  selected steps range from 350k to 1M, which confirms the final checkpoint is often not
  the best one. lr decay alone does not fix it (−55.4 ± 14.2).
- **Regression to report:** false disruption at ×1 rises to about 75% (round-2 winner 63%,
  v0 defaults 60% on validation). With compromise down to about 4%, most disruptive
  actions are precautionary. Uptime still improves (96% vs 90% for v0 defaults), so the
  cost is acceptable in this reward, but the stated goal of *lower* false disruption was
  not met.

Applying the rule: `r3_1m_dr_nstep3_sel` leads; only `r3_1m_dr_lrdecay_sel` is within one
std (−33.6 ≥ −38.0), and nstep3_sel has the lower robust db loss (1.8% vs 3.1%); its ×1
return (−22.5) beats v0 defaults (−91.8). **Final candidate: `r3_1m_dr_nstep3_sel`.**

## Final held-out result: protocol-v1

`python -m experiments.final --candidate configs/ddqn/r3_1m_dr_nstep3_sel.yaml --name protocol-v1`
trained the single selected candidate on seeds 0–4 (1M steps each, 999,000 gradient
updates, ~400 s per seed; checkpoint selection picked steps 500k, 700k, 950k, 650k and
950k), then ran the official held-out evaluation once and the held-out stress test. Full
comparison: [results/protocol-v1/COMPARISON.md](../results/protocol-v1/COMPARISON.md).

| Held-out, pooled (mean [95% CI over 5 seeds]) | v0 DDQN | **v1 DDQN** | threshold rules |
|---|---|---|---|
| Return | −65.6 [−72.1, −59.7] | **−29.1 [−32.1, −26.1]** | −96.0 |
| Compromise % | 47.5 [35.3, 58.9] | **7.1 [4.1, 11.2]** | 83.0 |
| db lost % | 9.8 [7.1, 11.9] | **1.1 [0.3, 2.1]** | 0.3 |
| Time to containment (steps) | 84.5 | **25.6** | 158.3 |
| Uptime % | 93.8 | 94.4 | 93.3 |
| Escalations / episode | 2.0 | 0.7 | 3.0 |
| False disruption % | **53.9** [45.8, 63.1] | 75.0 [69.6, 79.8] | 28.7 |

Stress test (held-out configs, every adversary probability × factor, seeds 3000–3049):

| Factor | v0 return | v1 return | rules return | v0 db lost % | v1 db lost % | rules db lost % |
|---|---|---|---|---|---|---|
| ×0.5 | −25.1 | −21.0 | −46.8 | 0.4 | 0.0 | 0.0 |
| ×1 | −66.9 | −30.6 | −97.1 | 9.5 | 1.7 | 0.7 |
| ×1.5 | −128.8 | −45.4 | −155.0 | 26.7 | 3.3 | 2.7 |
| ×2 | −198.2 | −60.5 | −204.1 | 44.8 | 6.5 | 4.7 |
| ×2.5 | −257.8 | −85.4 | −246.7 | 61.3 | 11.6 | 10.0 |

What this shows:
- v1 more than halves v0's held-out loss, cuts compromise from 47.5% to 7.1% and db loss
  from 9.8% to 1.1%, and contains attacks about 3× faster. The validation estimate
  (×1 −22.5 on training configs) and the held-out result (−29.1) agree in direction; the
  held-out configs are harder, as expected.
- v1 no longer collapses as attackers speed up: it beats the threshold rules on return at
  every factor, and its db loss now tracks the rules' instead of reaching 61%.
- **Where v1 is worse:** false disruption rises from 54% to 75% (rules: 29%). v1 acts early
  and often on nodes that are not yet compromised; uptime is still slightly higher than
  v0's because isolations are shorter and better targeted. The goal of *lower* false
  disruption was **not** met. The rules still lose the db slightly less often (0.3% vs 1.1%).
- Against held-out baselines (Holm-corrected): v1 is significantly better than the rules on
  return, compromise, containment, escalations and action cost, worse on false disruption,
  and not significantly different on uptime.

*Results are from a simulated environment and do not establish real-world effectiveness.*

### Possible next steps (not done)

- Target false disruption directly: e.g. a validation-selected `c_disrupt` sweep would change
  the reward, which requires a new env version (`-v1`) per docs/17, so it is out of scope here.
- Reward-preserving options: penalize disruptive actions in checkpoint-selection scoring, or
  add false disruption as a tie-breaker in the selection rule.
