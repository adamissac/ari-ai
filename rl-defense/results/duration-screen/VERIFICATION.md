# Historical verification corrections (post-run only)

PR #386 review identified two gaps: training aggregates were not rederived, and the
verifier used current product schema/metric code to interpret historical evidence.
Both are corrected without executing any policy, changing any measurements or revising
the failed-screen decision. No additional candidate or v11 preregistration.

Both verification entry points now recompute the complete validation summary **and**
`training`/`training_by_scenario` from their saved episodes. The full verifier additionally
reproduces every episode from all520 raw trajectories (15,600 transitions).

Historical interpretation uses `frozen/evaluation.py`, an evidence-only slice extracted
from the exact recorded commit `d985e69406fc7bcacabc1eea1b29f2c256c3803a`, not live product
imports. It contains the original transition schemas, episode metrics, aggregate/statistic
functions and fixed screen decision. Four complete source snapshots and their hashes
are retained beside it. `FROZEN.json` checks that each copied definition's canonical AST
matches the recorded original source; formatting changes do not change that comparison.
The executable slice itself is separately hash-pinned. It must never become production
policy logic or a second maintained implementation.

Use the recorded **Python3.12**, NumPy and Pydantic versions in `frozen/requirements.txt`.
The loader refuses a different Python minor or dependency version rather than silently
reinterpreting evidence. No current `rl_defense`, shared models, gateway or environment
is imported by the standalone verification path. Tests poison current product imports
and change current metrics/schema methods to prove historical verification is independent.

The pre-review index is preserved in `frozen/pre_review_index.json`. Original execution
source and the earlier reporting verifier are retained as non-executed source snapshots;
all other originally indexed artifacts remain byte-for-byte unchanged. The expanded index
verifies that complete history as well as the new reporting files. The current
`run_screen.py` changes its verification path only; the actual run remains pinned to the
original commit and original archived runner. Neither entry point replays the environment.

```sh
python results/duration-screen/run_screen.py --verify-only
python results/duration-screen/finalize.py
```

Regression tests also alter/re-pin stored training aggregates in a temporary copy: both
training aggregate sections must still fail semantic verification. This distinguishes
reproducibility checks from merely accepting a checksum manifest.
