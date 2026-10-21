# Alan → all: duration screen misses fixed criterion; stop before v11

### 2026-10-21 — RL-DURATION-001 screen complete; v11 not justified

Source `d985e69`, fixed/pushed plan before execution; all five heuristic/reference
policies completed 280 train and240 validation episodes,15,600 windows, no errors or
retries. Duration-aware vs actual v6 on validation: availability +1.2373 percentage
points,95% CI [−0.0313,+2.5340]; compromise −4.1464 points, CI [−7.4197,−1.1465].
Availability CI includes zero, failing the precommitted strict screen. Other validation
conditions pass, but training compromise also worsens vs v6 (16.3863% vs15.2552%).
Do not relax the test, add samples/candidates or prepare/launch v11. Reconsider the
objective/control design first. This is a deterministic heuristic, not trained RL.

All520 saved metrics exactly reproduce from complete raw trajectories; initial35
artifact pins and frozen source/actual registry verify. Expanded evidence additionally
pins post-run report/verifier. 13 focused tests passed in0.97s; Ruff lint/format and
diff checks pass. No holdout replay, new checkpoint, registration, serving change or
promotion. V6 registry unchanged. Results in `rl-defense/results/duration-screen`.
PR #386 holds the complete source/results; final review and CI pending.
