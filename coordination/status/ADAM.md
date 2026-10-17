# Adam — implementation status

Owner: Adam
Branch: `feat/adam/rl-defense`
Current task: RL improvements (training worker on `feat/adam/rl-training-v1`) + platform integration adapters
Last remote sync: 2026-10-17 — origin/main at `945afc9`; no other branches, PRs or issues yet
API/contract dependencies: `DefenseRecommendation`, `PlatformFacts`, `RLCheckpointRef`, `RLEvaluation` proposed to Srihith in `coordination/messages/20261017T001311Z-adam-to-srihith-rl-recommendation-contract.md`; local adapter in `rl-defense/rl_defense/contracts.py` until `shared/` V0 merges
Verified tests: `cd rl-defense && .venv/bin/python -m pytest -q` → 52 passed (CPU, macOS arm64, Python 3.12, torch 2.14.1, gymnasium 1.4.0); ruff check + format clean
Recent PR/commit: PR #1 https://github.com/adamissac/hackatl-agentic-security/pull/1 (code `1182773`); contract issue #2
Blockers: none for RL; backend endpoint and Defense Lab UI need `shared/` V0 and backend persistence
Next action: adopt `shared/` models when Srihith publishes V0; then RL-101 ablations (vanilla DQN vs DDQN, feature and reward sensitivity)

## Session entries

### 2026-10-17 (later) — analysis, platform mapping, Defense Lab bundle, stress test
- **Added:** per-step reward components (returns bit-identical to v0), failure-case analysis with
  deterministic replays (`results/protocol-v0/ANALYSIS.md`), `platform_mapping.facts_from_platform`
  (validated open findings, expectation sensitivity and labeled signals → policy inputs, with
  provenance), a typed Defense Lab bundle + JSON Schema for Vihaan, and an aggressiveness stress test.
- **Findings (simulation only):** DDQN loses the db in 9.8% of held-out episodes vs 0.3% for the
  rules; under faster attackers (×2.5) its db loss rises to 61% vs 10% and it falls behind on
  return. These drive the current training experiments (aggressiveness randomization).
- **Fixed:** observation size documented as 47 — it is 48 (correction posted on issue #2).
- **CI:** green on every pushed commit (`rl.yml`).

### 2026-10-17 — RL-001…RL-004 implemented, RL-005 adapter ready
- **Built:** `DefenseSimEnv-v0` (Gymnasium; 48-dim observation, 22 masked actions, hidden
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
