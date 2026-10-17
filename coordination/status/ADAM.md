# Adam — implementation status

Owner: Adam
Branch: `feat/adam/rl-defense`
Current task: RL-005 integration (backend endpoint + UI panel depend on Srihith / Vihaan)
Last remote sync: 2026-10-17 — origin/main at `945afc9`; no other branches, PRs or issues yet
API/contract dependencies: `DefenseRecommendation`, `PlatformFacts`, `RLCheckpointRef`, `RLEvaluation` proposed to Srihith in `coordination/messages/20261017T001311Z-adam-to-srihith-rl-recommendation-contract.md`; local adapter in `rl-defense/rl_defense/contracts.py` until `shared/` V0 merges
Verified tests: `cd rl-defense && .venv/bin/python -m pytest -q` → 36 passed (CPU, macOS arm64, Python 3.12, torch 2.14.1, gymnasium 1.4.0); ruff check + format clean
Recent PR/commit: see PR on `feat/adam/rl-defense` (code commit `1182773`)
Blockers: none for RL; backend endpoint and Defense Lab UI need `shared/` V0 and backend persistence
Next action: adopt `shared/` models when Srihith publishes V0; then RL-101 ablations (vanilla DQN vs DDQN, feature and reward sensitivity)

## Session entries

### 2026-10-17 — RL-001…RL-004 implemented, RL-005 adapter ready
- **Built:** `DefenseSimEnv-v0` (Gymnasium; 47-dim observation, 22 masked actions, hidden
  stage adversary), 3 train + 3 held-out configs, masked Double DQN, baselines, checkpoint
  manifests, protocol-17 evaluation, typed simulation-derived recommendation adapter, `rl.yml` CI.
- **Executed:** 5 seeds × 200k steps (199,000 gradient updates each, ~72 s/seed CPU) and full
  evaluation (4 policies × 5 seeds × 3 held-out configs × 100 episodes). A clean retrain from
  commit `1182773` reproduced identical per-seed metrics.
- **Result (simulation only):** DDQN return −65.6 [−72.1, −59.7] vs threshold rules −96.0,
  random −154.3, noop −386.2. Compromise 47.5% vs rules 83%. DDQN is worse than the rules on
  false disruption (54% vs 29%) and worse than random on compromise (random: 8.9%, at 41% uptime).
  Full table: `rl-defense/results/protocol-v0/eval_table.md`.
- **Bug found and fixed:** the random baseline re-seeded from the episode seed only, so all
  five random "seeds" were identical; fixed and re-evaluated (conclusions unchanged).
- **Not done / unverified:** backend endpoint and UI panel (other owners); live provider not
  applicable to RL; real-world transfer is not claimed (RQ-005).
