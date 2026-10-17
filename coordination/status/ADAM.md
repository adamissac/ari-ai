# Adam — implementation status

Owner: Adam
Branch: all work merged to `main` (last: PR #13 shared contracts, PR #18 recipe check)
Current task: RL training improvements (worker branch `feat/adam/rl-training-v1`, merging to main every round)
Last remote sync: 2026-10-17 — origin/main at `945afc9`; no other branches, PRs or issues yet
API/contract dependencies: `DefenseRecommendation`, `PlatformFacts`, `RLCheckpointRef`, `RLEvaluation` proposed to Srihith in `coordination/messages/20261017T001311Z-adam-to-srihith-rl-recommendation-contract.md`; local adapter in `rl-defense/rl_defense/contracts.py` until `shared/` V0 merges
Verified tests: `cd rl-defense && .venv/bin/python -m pytest -q` → 52 passed (CPU, macOS arm64, Python 3.12, torch 2.14.1, gymnasium 1.4.0); ruff check + format clean
Recent PR/commit: PR #1 https://github.com/adamissac/hackatl-agentic-security/pull/1 (code `1182773`); contract issue #2
Blockers: none for RL; backend endpoint and Defense Lab UI need `shared/` V0 and backend persistence
Next action: adopt `shared/` models when Srihith publishes V0; then RL-101 ablations (vanilla DQN vs DDQN, feature and reward sensitivity)

## Session entries

### 2026-10-17 — HANDOFF (owner usage ending): exact state for the next session
- **On main:** RL env/DDQN/baselines/eval/analysis/stress/explain/lab export (PR #1), payments-lite
  (#5), link+secret CI (#7), shared V0 + backend (#8, verified with the backend + RL suites), RL
  contracts re-exported from `shared.rl` (#13), training improvements round 1–2 (#15), build-recipe
  consistency check (#18). RL suite on main: 80 passed. Backend: 40 passed, 1 skipped (live opt-in).
- **Done since:** protocol-v1 merged to main (held-out return −29.1 vs −65.6, db loss 1.1% vs
  9.8%; false disruption worse, 75%); audited from raw episodes; Defense Lab bundle + fixture
  regenerated from v1. Current policy: `runs/protocol-v1/ddqn_seed0.pt`.
- **Next steps:** (1) reduce false disruption without losing the v1 gains (new validation round);
  (2) decide checkpoint storage with Srihith (`RL_CHECKPOINT_PATH`); (3) run failure analysis on v1.
- **Open asks:** Alan — real path templates in `build_recipe.json` (#17); Sarosh — attach the
  ownership expectation to `GET /payments/{payment_id}` (review on #6); Srihith — pass expectations
  into `facts_from_platform` for criticality (review on #8).

### 2026-10-17 (integration) — contracts verified, cross-pillar checks
- shared V0 RL contract verified field-for-field against #8 (`tests/test_shared_contract.py`, 6/6);
  local DTOs now mirror shared ID formats; ack posted (#9).
- Re-ran Srihith's `backend/tests/test_rl_integration.py` (real embedded Postgres) against
  `feat/adam/rl-defense` @ `c197381`: **2 passed**.
- Reviewed #8 (RL parts): asked for expectations → criticality wiring and the real
  `POST /refunds` route. Ran Sarosh's indexer (#6) on payments-lite: 8/8 entry points and the
  refund invariant found; the ownership rule is not attached to `GET /payments/{payment_id}`
  (feedback posted with a sibling-convention suggestion).
- New: `explain()` occlusion explanations; `accepted_risk` counts as open exposure.
- Other PRs from me: #5 payments-lite (DEMO-001), #7 link + secret CI (INFRA-003),
  #10 API-key setup instructions (no key in GitHub).

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
