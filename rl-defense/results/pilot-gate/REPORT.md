# Pilot gate result: frozen v6 does not pass

_Measured against the owned demo app in the isolated in-process lab. Lab evidence only._

Pre-registration: [`PREREGISTRATION.md`](PREREGISTRATION.md), committed as `b851b88d` before
the run. One run, 2026-11-14, 4 frozen scenarios x 30 episodes, every policy on the same
episodes. Raw rows: [`episodes.json`](episodes.json); everything else:
[`summary.json`](summary.json); hashes: [`EVIDENCE.json`](EVIDENCE.json).

**Verdict: FAIL (8 of 9 checks pass). The RL-gated pilot stays blocked.**

| Check | Value | Required | Result |
|---|---|---|---|
| Paired return gain over the rules, 95% CI low | +0.090 | > 0 | pass |
| Compromise rate | 0.090 (rules 0.175) | <= rules | pass |
| Availability | 0.901 | >= 0.85 | pass |
| Delegated success | 0.873 | >= 0.85 | pass |
| False disruption | 0.063 | <= 0.25 | pass |
| Attack-free defense duty | 0.263 | <= 0.5 | pass |
| Return | -5.08 (rules -5.54) | > rules | pass |
| Worst per-scenario return difference against the rules | **-0.510** | >= 0 | **fail** |

Pooled:

| Policy | Return | Compromise | Availability | Delegated success | False disruption |
|---|---|---|---|---|---|
| candidate v6 | -5.08 | 0.090 | 0.901 | 0.873 | 0.063 |
| threshold_rules | -5.54 | 0.175 | 0.932 | 0.931 | 0.034 |
| always_block_principal | -4.77 | 0.120 | 0.925 | 0.912 | 0.034 |
| always_block_principal_long | -4.90 | 0.066 | 0.899 | 0.869 | 0.065 |
| always_block_top_principal_long | -5.31 | 0.122 | 0.901 | 0.869 | 0.065 |
| noop | -14.79 | 1.000 | 1.000 | 1.000 | 0.000 |

Per scenario (return / compromise / availability / delegated success):

| Scenario | candidate v6 | threshold_rules |
|---|---|---|
| pilot_always_on_customer | -4.26 / 0.000 / 0.862 / 1.000 | -4.44 / 0.007 / 0.862 / 1.000 |
| pilot_insider_three_victims | -10.08 / 0.126 / 0.768 / 0.618 | -10.60 / 0.480 / 0.874 / 0.795 |
| pilot_outsider_trio_rotation | **-4.63** / 0.129 / 0.915 / 1.000 | **-4.12** / 0.083 / 0.912 / 1.000 |
| pilot_quiet_heavy_books | -1.36 / 0.444 / 1.000 / 1.000 | -3.00 / 1.000 / 1.000 / 1.000 |

## Reading

- v6 is a better defender than the tuned rules overall: half the compromise rate and a
  higher return, inside every pooled floor.
- It fails because on the three-attacker rotation scenario it is worse than the rules on
  both return and compromise. The rule that no scenario may regress exists so that a pooled
  win cannot hide a case where the learned policy is the worse choice; this is such a case.
- Not gated but worth knowing: on the insider scenario v6 lets only 62% of authorized
  delegated reads through and blocks legitimate traffic in 71% of attack-free windows. The
  pooled floors hold only because the other scenarios are clean.
- The fixed baseline `always_block_principal` has a better pooled return than v6 (-4.77 vs
  -5.08) with higher availability and delegated success. A learned policy is not yet buying
  anything over a one-line rule here either.
- Abstention: v6 took no action in 100% of the 1,844 windows without a flagged principal,
  and acted in 25% of the 1,756 windows with one.
- Uncertainty: harm rate by Q-margin tercile is 0.142 (low), 0.199 (mid), 0.207 (high). A
  small margin does not go with more harm, so the Q-margin is not usable as a confidence
  signal. Q-values are scores, not probabilities.

## Consequences

- `backend/backend/live_defense/readiness.py` reads this bundle by hash and reports
  category F as FAIL with the number above. No category is PASS and `ready` is false.
- These four scenarios are exposed. A future candidate needs new frozen scenarios and a new
  pre-registration.
- RL stays where it is in live defense: a shadow recommender whose output is recorded and
  never executed, with the deterministic rules as the authority.
