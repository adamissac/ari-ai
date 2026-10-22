# Duration screen: do not prepare v11

The fixed screen **failed** its availability-improvement confidence condition. Do not
relax that condition, enlarge this validation sample post hoc, try a second candidate
or prepare/launch v11 from these results. V6 and its actual registry remain unchanged.

## What ran

Source `d985e69406fc7bcacabc1eea1b29f2c256c3803a` and the [plan](PLAN.md) were
committed/pushed before execution. The tracked source fingerprint stayed unchanged
through all workers and completion. Started2026-10-21T19:09:56.344446Z; finished
19:10:54.430022Z, about58 seconds. Five CPU workers, no failed jobs or retries.
Runtime, source/config/registry/reference hashes and exact commands are in [RUN.json](RUN.json).

All five policies completed all56 training episodes (7 scenarios ×8 seeds), followed
by all48 validation episodes (3 scenarios ×16 seeds): **520 episodes and15,600 windows**.
The duration candidate reuses the existing outsider rule: long blocks for flagged
principals with no observed authorized traffic, short otherwise, broad fallback controls
disabled. It uses operator-visible traffic, not hidden attack labels. A zero observed
own/authorized share does not prove that a principal has no legitimate traffic.

This is a deterministic **heuristic** comparison. No DDQN was trained, new checkpoint
created, production policy changed, model registered or approval fabricated. Existing
val_v10 is a previously used selection set, not fresh held-out evidence. No holdout
configuration was loaded or executed by this runner.

## Validation against actual v6

- Availability: candidate88.2140%, v6 86.9766%; difference **+1.2373 percentage points**,
  paired stratified-bootstrap95% CI **[−0.0313, +2.5340] points**. The interval includes
  zero, so the precommitted strictly-positive lower bound **fails**.
- Compromised attack-request fraction: candidate10.1606%, v6 14.3071%; difference
  **−4.1464 points**, 95% CI **[−7.4197, −1.1465] points**. This condition passes.
- Every validation scenario's point compromise fraction is no worse than v6; candidate
  pooled availability exceeds85%. These conditions pass, but all conditions were required.

The availability point estimate is encouraging but uncertain; this is not evidence of
"no benefit." It is insufficient to meet this fixed screen. No threshold was widened.
The intervals resample paired **evaluation episodes** within scenario (10,000 resamples,
seed1), recomputing pooled request-weighted fractions. They do not quantify variability
across training seeds or establish held-out/real-world effectiveness. All policy and
scenario metrics are in [summary.json](summary.json).

## Short/long comparison on training cases

Across56 training episodes, short blocks have94.0993% availability and21.6647% compromise;
long blocks90.9574% availability and9.0197% compromise. Duration-aware blocks reach
93.6525% availability and16.3863% compromise, compared with v6 92.1277% and15.2552%.
Thus the candidate **does worsen pooled training compromise versus v6**, despite the
better validation point estimates. This instability also counsels against another long run.

For `insider_delegate`, short and duration-aware controls give89.5833% availability /
15.0943% compromise, while long gives84.1667% /10.3774%. For
`two_identities_delegated`, duration-aware gives85.4688% /37.5000%, short87.9167% /
57.2368%, long80.5208% /11.8421%. Shortening blocks protects legitimate traffic but
allows more retries; merely switching duration does not eliminate that tradeoff.
These are fixed training-scenario measurements, not independent learned-policy evidence.

## Verification and limits

All35 initially indexed files verified. All520 saved episode metrics reproduce exactly
from the complete raw trajectories (schema-validated15,600 transitions), with no policy
or environment replay. Source and actual registry hashes matched launch metadata before
post-run reporting. Stored validation summary regenerates exactly from saved episodes.
Post-run reporting adds this report and a raw-trace verifier to the artifact manifest;
execution code/plan, existing metrics and trajectories stay unchanged.

From `rl-defense`, using the documented workspace RL runtime/PYTHONPATH:

```sh
python results/duration-screen/run_screen.py --verify-only
python results/duration-screen/finalize.py
```

The first command verifies pins and statistics; the second additionally reconstructs
metrics from saved traces. Neither executes policies. The original output directories
are retained; the runner refuses overwrite/restart. This is the owned in-process
payments-lite lab, not real-world effectiveness proof.

## Decision and next design work

No v11 preregistration or long training run. The one fixed candidate did not meet its
screen, and training compromise worsened. Reconsider the objective/control design
before further experiments: aggregate recent authorized-share observations do not
establish a principal's future legitimate-traffic needs, and principal-wide controls
necessarily deny authorized reads while active. A request-scoped control would require
separate design/contract review; it is not silently substituted here. Additional
candidates, tuning or more samples are outside this completed screen.
