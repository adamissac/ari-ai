# Alan → all: V9 review fixes and V10 preregistration

Owner explicitly authorized merging #375/#376 and the three proposed follow-ups.
#375's documentation conflicts are resolved; #376 addresses all five automated review
findings. Historical v9 reports/measurements remain unchanged; 77-artifact bundle and
all seed indices verify. Merge after required checks.

Branch `feat/alan/v10-demo-balance`: saved-v9 analysis, opt-in demonstration action
class balancing, real tiny training/regression tests and fresh two-arm preregistration.
No shared contract or serving policy changes; all default replay remains uniform.
~87% teacher noops suggest imbalance but do not establish causality. Worst trace has
20 compromised windows with available block actions ranked below noop.
Fresh val/holdout configs are unexecuted. Future study: uniform versus balanced,
5 fixed seeds each, same budgets, actual v6 baseline, ~6h CPU/33k evaluated episodes.
No training launch or promotion in this session. V6 remains deployed.
