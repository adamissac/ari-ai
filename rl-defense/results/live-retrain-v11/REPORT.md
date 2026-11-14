# v11: the validation prediction failed; the gate was not run

_Measured against the owned demo app in the isolated in-process lab. Lab evidence only._

Pre-registered in `results/pilot-gate-v2/PREREGISTRATION.md` (`eebf1fe7`). One training run,
seed 0, 150,000 live steps on `train_v11`. Checkpoint sha256
`046c64392e3729728892959c54f010278ff905a336a54b0241ba5dfd655c960a` is recorded in `candidate_v11.manifest.json`; the weights are not committed because
the candidate is not eligible for anything.

**Prediction:** availability >= 0.85 on validation and no validation scenario below the
re-tuned rules. **Result: availability 0.937 (holds); trails the rules on 4 of 6 scenarios
(fails).** Gate v2 was not run and its four scenarios remain unexposed.

| Validation scenario | v11 | re-tuned rules |
|---|---|---|
| val11_delegate_two_victims | -11.20 | -11.20 |
| val11_trio_switch | -6.03 | -5.88 |
| val3_mixed | -8.86 | -7.74 |
| val4_rogue_delegate | -8.82 | -7.61 |
| val4_rotation_start | -10.25 | -6.23 |
| val4_slow_insider | -8.01 | -12.87 |

## Diagnosis (validation and already-exposed data only)

Same 48 validation episodes for every policy ([`val_comparison.json`](val_comparison.json)):

| Policy | Mean return | Compromise | Availability |
|---|---|---|---|
| always_block_principal_long | **-5.83** | 0.114 | 0.874 |
| frozen v6 | -7.35 | 0.259 | 0.881 |
| always_block_principal | -7.97 | 0.382 | 0.915 |
| rules tuned for v6 | -8.42 | 0.317 | 0.912 |
| rules re-tuned on train_v11 | -8.59 | 0.360 | 0.926 |
| v11 | -8.86 | 0.450 | 0.937 |

- **The teacher was the wrong one.** The teacher is chosen by train return over 2 episodes
  per scenario. That picked the re-tuned rules (-4.63 against -5.13 for
  `always_block_principal_long`), but on validation the long block is better than the rules
  on all six scenarios. v6's teacher was the long block. v11 learned from the weaker teacher
  and its validation return barely moved from the pretrained network (-9.78 to -8.86).
- **The fixed long block beats both learned policies on validation**, and on the first
  gate's saved episodes it satisfies all nine checks where v6 fails one. That second fact is
  post hoc on exposed data: it is a reason to test the rule, not a gate pass.
- The availability-aware selection did what it was for: every snapshot met the floor.
