# V9 failure analysis and V10 candidate intervention

Implemented analysis reads saved v9 experience, reports and traces only. No held-out
episode was replayed. `analyze_v9.py` regenerates `v9_diagnostics.json` using the original
selected seed0 checkpoint; Q values are model inference on saved observations.

All five teacher datasets contain4,200 rows: noop counts3666,3670,3682,3696,3652;
short-block counts150,151,153,143,156; long-block counts384,379,365,361,392. Uniform
demonstration replay consequently devotes about87% of its samples to noop.

The worst recorded episode (seed0, faint outsider40783) compromises23 of23 attack
requests. In20 of those windows, the previous transition's next-action mask shows a
principal block was already available at the decision point. All20 saved-observation
Q evaluations rank noop above every available principal-block action. The selected
seed0 noop margin is0, so this is not abstention introduced by a positive margin.
The other3 compromised windows arrive without a previously flagged target; this
one-window observation delay is expected, not a demonstrated mask defect. A transition
stores its NEXT mask; using its own mask for its action incorrectly yields23 available
windows. The analysis explicitly uses the preceding transition's mask.

Mixed rotation's aggregate candidate return is−13.07582 versus v6−12.70970. All five
seed deltas and every decision/Q value are retained. This confirms an observed failure,
not a causal explanation of the neural network's training. No serving or timer bug was
established, and no deterministic fallback is inserted into the learned policy.

Candidate intervention: opt-in uniform sampling over observed demonstration action
classes, then uniform rows within the chosen class. This preserves real transition
associations and teacher labels while giving rare block/extension examples representation.
It changes their training weight and may also amplify teacher mistakes; effectiveness
remains an untested hypothesis until the preregistered two-arm v10 study completes.
Agent replay, rewards, action permissions, demonstrations, gradient budgets and production
recommendations remain unchanged. Default replay retains its exact original RNG sequence.

Regression tests cover rare-class representation, row integrity, seeded sampling, ring
overwrite/single-class/empty buffers, default compatibility, real tiny training gradients
and checkpoint lineage, separate-arm aggregation, complete gates and fresh split hygiene.
No v10 holdout is executed in tests. Preregistration defines a future ten-run comparison
(5 seeds/arm), not a completed result. V6 remains deployed.
