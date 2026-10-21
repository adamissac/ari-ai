# V10 follow-up: stop and diagnose before another experiment

**Decision: do not launch v11.** The owner authorized diagnosis and at most one targeted
follow-up experiment, conditional on an evidence-backed fix and a testable prediction.
The current correction prevents an already-ineligible model from consuming fresh holdout;
it does not demonstrate improved policy behavior. Another six-hour training run is not justified yet.

## Findings from saved evidence

All ten selected v10 checkpoints already fall below the unchanged 85% availability
floor on validation (82.48–84.94%). The selector maximizes mean return and does not
require this floor. All five balanced seeds' recorded best-margin snapshots miss it.
Only uniform seed2 has a recorded best-margin snapshot that meets the floor; it was
not selected. History retains only the best-return margin at each snapshot, so this
**does not prove that every evaluated margin or unretained checkpoint is infeasible**.
Validation performance does not establish held-out performance; the screen is only a
necessary research check for this proposed workflow, not a replacement promotion gate.

On the exposed rotation scenario, short-block baseline mean return is −12.7698 versus
−14.9712 for long blocks; benign availability is 72.15% versus62.61%. Balanced candidates
average63.97% availability versus69.98% for v6. These saved comparisons identify a
control-duration tradeoff. They do not prove the best intervention, infeasibility of
all policies, or generalization to another holdout.

The worst balanced-minus-v6 rotation episode is balanced seed0, evaluation seed43341.
Candidate return−13.66 versus−7.10; 5/20 compromised requests versus9/20, at the cost of
126/369 benign requests blocked versus46/369. During attack-free windows, the candidate
blocks107/317 benign requests versus28/317. Its actions are two long principal blocks,
one short block and27 noops. Both complete saved traces are in [diagnostics.json](diagnostics.json).

A focused gateway regression confirms the mechanism independently using synthetic fixture
requests: blocking a principal contains both primary and rotated tokens, but also denies
that principal's own reads and authorized delegated reads. Clearing that control restores
normal own reads. No existing gateway semantics are changed; the principal-wide block
is behaving as documented. This is not evidence of a token-rotation bypass.

## Implemented correction

`online --require-validation-availability` checks the selected snapshot's recorded
validation availability against `PromotionCriteria.min_availability`, before creating
or executing any held-out policy/trajectory output. A missing, nonfinite, invalid or
below-floor metric is rejected. Selected step/margin must match exactly one history
entry. Rejection writes `validation_screen.json` and raises an explicit error while
leaving the trained checkpoint/experience intact. Eligible screening is not promotion.
The flag is opt-in; old experiments/default training and serving behavior are unchanged.
On a successful flagged run, the screen is embedded in the promotion report. This
correction would have stopped all ten v10 selections before holdout execution.

## Verification and reproducibility

`analyze.py` reads existing manifests, episode summaries and one saved trajectory
container. It never calls a policy or environment. All inputs are SHA-256 pinned in
[diagnostics.json](diagnostics.json). Run from repository root with the workspace RL
Python and `PYTHONPATH=rl-defense:shared:standards:examples/payments-lite/target`:

```sh
python rl-defense/results/v10-followup-diagnosis/analyze.py
python -m pytest rl-defense/tests/test_live_validation_screen.py -q
```

Tests cover rejected/invalid metrics, exact-floor eligibility, ambiguous selected
lineage, fail-before-holdout execution, explicit CLI opt-in, actual v10 checkpoint
screens, input pins, and token rotation/own/delegated access. Existing v10 evidence is
preserved unchanged. No holdout was replayed, new training launched, policy registered
or registry changed. This is an owned in-process payments-lite lab, not proof of
real-world effectiveness.

## Before any further long run

Choose one research intervention that addresses the documented cost of principal-wide
control (for example, validation-constrained selection or a duration-aware learning
objective). Demonstrate improvement on train/validation fixtures with unchanged business
access assertions, retain all alternatives/failures, and preregister one prediction on
fresh data. A request-scoped enforcement action would require a separate design/contract
review; it is not silently substituted for existing principal blocking. If a targeted
experiment still fails, revisit the objective/control design before another version.

Focused verification: 22 tests passed in 22.51s, including the unchanged complete v10
evidence bundle. Ruff lint/format and diff checks pass. No new policy execution or
training performed by this diagnosis. Full CI and review pending.
