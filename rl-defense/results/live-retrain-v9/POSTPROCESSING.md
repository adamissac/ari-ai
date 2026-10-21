# V9 reporting and evidence verification

The learning experiment is frozen at `29aa5f8`. Reporting helpers are developed on the
separate `feat/alan/v9-reporting` worktree while the five jobs run. They are integrated
only after the cohort finishes. They do not change the learning code, config, budgets,
selection rule or held-out results.

Reporting tests use synthetic files only. Default RL tests require no plotting package.
The optional figure renderer uses an isolated Matplotlib 3.11.2 installation; it does
not modify the training virtualenv. Numeric intervals are computed in the training
runtime before rendering. Plotting only reads `figure_data.json`.

## After all five seeds finish

From `rl-defense`, with its Python interpreter and the workspace `PYTHONPATH` used for
the run:

```sh
python results/live-retrain-v9/report_study.py
python results/live-retrain-v9/prepare_plot.py results/live-retrain-v9
# Optional: use a separate environment with matplotlib==3.11.2, Agg backend.
python results/live-retrain-v9/render_plot.py results/live-retrain-v9
python results/live-retrain-v9/finalize_study.py results/live-retrain-v9 \
  --registry-snapshot /path/to/captured/registry.json \
  --environment /path/to/captured/environment.json \
  --observed-progress /path/to/observed/progress.json
```

The first command runs the predeclared **train-only** platform checks and reads saved
held-out metrics/trajectories to find the worst paired episode. No held-out policy is
executed by reporting. The finalizer checks preregistration identity, reports secondary
quiet/flagged-window thresholds, and pins sidecars, metrics, rules and compressed raw
traces alongside checkpoint/experience hashes. Run it last after all report files are
final, since `STUDY_EVIDENCE.json` pins every saved file in the evidence directory.

The captured registry snapshot must match the launch digest. Snapshot/default paths
in a published bundle are local to that bundle; no access to the original owner's
machine is needed for later verification.

## Read-only verification of the published bundle

```sh
python results/live-retrain-v9/finalize_study.py results/live-retrain-v9 --verify-only
```

This verifies the saved artifact hashes and all five compressed evidence indices.
It does not retrain, repeat held-out evaluation, edit the bundle or promote a policy.
Digest checking is not a report signature or an authenticated approval service.

The evidence index hashes the logical uncompressed trajectory JSONL stream; the original
promotion report also pins the gzip container bytes. Restored JSONL duplicates are
git-ignored and excluded from the stored-file manifest, so verification stays portable
after a local restore.

## Post-run review guards

The five historical promotion reports remain byte-for-byte unchanged. They predate the
explicit `rules_episodes` field; re-aggregation now requires `legacy_rules_episodes`
per seed, taken from each saved `command.json` (all2). Expert choice, training scores
and rules parameters must also match. Missing source commits and missing/extra
per-policy holdout scenarios are refused. Strict re-aggregation reproduces every
original numeric result. New online reports include the teacher budget directly.

`reference_pins.py` pins the historical v7/v8 bytes in both launcher and reporter.
This is a post-run integrity guard, not a claim that the original launcher checked it.
All five saved reports already identify those exact digests. Generic evidence packing
now verifies/indexes recorded trajectories immediately, before removing plain logs.

The published historical cohort is reproducible through the CLI (output outside the
immutable bundle): `python -m rl_defense.live.study results/live-retrain-v9/seed*/promotion_report.json --legacy-rules-episodes 2 --out /tmp/v9-summary.json`. The explicit historical budget comes from all five pinned `command.json` files. New reports need no legacy flag. The runner now refuses dirty/unknown source, and aggregation validates actual pooled/per-scenario episode counts.
