# RL follow-up: fail-closed live gate, v6 shadow fix, reward-v1 result

From: Claude (agent, for Alan). To: Adam, Srihith. PR #941.

- `rl_defense/live/evaluate.py::promotion_decision` now rejects when a metric is undefined, when rules rows are missing under `must_beat_rules`, or when candidate/deployed/rules are not on identical `(scenario, seed)` sets. New first check: `paired_episode_sets_match`. Committed reports are untouched.
- `rl_defense/live/registry.py`: atomic save; rollback verifies the target bytes.
- `backend/backend/live_defense/policy.py` (Adam): `alert_rate` is `status_4xx + status_5xx`; `auth_failures` was added on top although it is a subset of `status_4xx`.
- `RewardParams.c_false_disrupt` is a new optional field (default 0, v0 hashes unchanged). No shared contract changed.
- Result to know: charging for benign disruption cut it from 72% to 41% and raised compromise from 16% to 71%. No policy is recommended. A simple rule (`ExposedGuardPolicy`) matches or beats the DDQN at 300k steps.
