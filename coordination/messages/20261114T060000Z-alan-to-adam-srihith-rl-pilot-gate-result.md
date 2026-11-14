# RL pilot gate: thresholds approved by Alan, one run, v6 failed

From: Claude (agent, for Alan). To: Adam, Srihith.

- Alan approved pilot-gate thresholds on 2026-11-14: `rl-defense/configs/live/promotion.yaml` plus delegated success >= 0.85, tuned rules as incumbent. Adam: this was decided without you in the room; object on #559 if you disagree.
- One pre-registered run (`rl-defense/results/pilot-gate/`): frozen v6 passes 8 of 9 checks and fails `no_per_scenario_regression` (-0.510 on `pilot_outsider_trio_rotation`). Gate stays blocked.
- `backend/backend/live_defense/readiness.py` (Adam's area) now reads that bundle by pinned hash. It can set FAIL and add notes; it cannot set PASS. Without the bundle the endpoint is unchanged.
- Srihith: no shared contract changed. `RlEvaluationMetricSpec.threshold` is still null and `threshold_status` still `pending_rl_owner_approval`, which is now out of date. Recording approved thresholds there needs a contract change I did not make.
