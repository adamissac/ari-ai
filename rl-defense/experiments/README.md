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

_Filled in as rounds complete._
