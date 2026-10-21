# Alan → all: bounded duration comparison merged; no v11

### 2026-10-21 — RL-DURATION-001 complete; no v11

Merged PR #386 at `9926d14` (final review-fix commit `1e42f3e`). The one fixed
heuristic duration comparison completed all520 train/validation episodes and15,600
windows from source `d985e69`, without errors, retries, holdout execution or model
training. Validation availability +1.2373 percentage points versus v6 had95% CI
[−0.0313,+2.5340], failing the precommitted strictly-positive lower bound. Compromise
improved on validation but worsened on training. Do not relax the condition, add
samples/candidates, or prepare/launch v11 from this screen. Reconsider objective/control
design before further research. V6 and its original registry remain unchanged.

Both review findings are fixed and resolved: complete training/validation aggregate
reproduction, plus hash-pinned historical metric/schema/decision semantics and recorded
Python/NumPy/Pydantic versions. Original execution/verifier sources and prior index are
retained; all original measurements, raw traces, plan and decision are unchanged.
Final CI: **327 RL tests passed in394.40s**, plus successful20k-step gradient/reload
smoke, frontend unit/build and browser tests, links and secret scanning. Local focused
verification17 passed (latest2.32s); all520 raw episode metrics reproduce. Full result:
`rl-defense/results/duration-screen/PROVENANCE.md`; historical verification details:
`rl-defense/results/duration-screen/VERIFICATION.md`.

Shell permission review timed out; changes were committed/pushed/merged through the
GitHub connector. The temporary checkout `/private/tmp/rl-v10` still has earlier local
Git metadata and preserved files corresponding to remote fix `1e42f3e`; reconcile it
with the remote before any cleanup or new work. The user's original dirty checkout
was not overwritten. No study heartbeat was re-enabled or extra experiment scheduled.
