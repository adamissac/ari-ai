# `rl_defense.live` — the live defense loop and live retraining

Closes the loop the simulator cannot: a **trained DQN observes real telemetry** from the
owned demo app, **executes a permitted defensive action** that really takes effect,
**measures the actual outcome**, and **records a reward + training transition**. This is
the first code path in the project from a real application to an observation, from a
recommendation to an enforced action, and from a measured outcome back to a reward.

## The loop

```
reset(): start payments-lite in-process behind the gateway, drive one warm-up window
step(action):
  1. apply the permitted action to the gateway's enforced controls
  2. drive one window of REAL benign + attack HTTP traffic through the gateway
  3. measure the real outcome (compromised cross-tenant reads; blocked benign requests)
  4. reward = f(measured counts)         # not from any hidden state
  5. build next observation from measured telemetry (-> from_platform_facts -> 48-dim obs)
  6. return a replay-buffer-shaped LiveTransition
```

| Module | Role |
|---|---|
| `gateway.py` | `DefensiveGateway` wraps the target ASGI app; enforces `isolate`/`rate_limit`/`raise_monitoring` and (v2) principal blocks for real; records every request's true outcome. |
| `actions.py` | Live action spaces v2 (`block_principal`, index 22) and v3 (`block_principal_long` 23, `block_top_principal_long` 24, six detector features); widens narrower checkpoints without changing their choices. |
| `telemetry.py` | Real request records → `PlatformFacts` (measured `alert_rate`, `anomaly_score`). |
| `adversary.py` | `TrafficDriver`: real benign traffic + real cross-tenant attackers abusing the planted BOLA in `GET /payments/{id}` (one or more identities, optional token rotation; fixture tenants in `IDENTITIES`). |
| `loop.py` | `LiveDefenseLoop`: the episode harness; loads any checkpoint via the existing `PolicyRunner`. |
| `contracts.py` | `LiveTransition`, `StepOutcome`, `DefenseControls` (local realization of the PROPOSED shared experience schema). |
| `run.py` | CLI: train-or-load a policy, run N live episodes, write transitions + a summary. |
| `scenarios.py` | Versioned, hashed live scenarios (`configs/live/{train,val,holdout}`) with disjoint seed bands. |
| `experience.py` | Collects ε-greedy experience on **train** scenarios into a SHA-256-pinned JSONL dataset. |
| `retrain.py` | Offline Double-DQN retraining of a **candidate** from datasets; warm start from the deployed checkpoint; selection on **val**. |
| `evaluate.py` | Paired held-out metrics, live-tuned threshold rules, and the deterministic promotion gate. |
| `registry.py` | Versioned policy registry: human-approved (`usr_*`) promotion bound to a passing report, rollback. |
| `pipeline.py` | Rounds of collect → retrain → val selection, then one held-out verdict and report. |

## Run it

```sh
cd rl-defense
PYTHONPATH=.:../shared:../standards:../examples/payments-lite/target \
  .venv/bin/python -m rl_defense.live.run --steps 30000 --episodes 3 --horizon 30 \
  --out results/live-slice/transitions.jsonl
```

Reference output of this exact command is in
[`results/live-slice/run_output.txt`](../../results/live-slice/run_output.txt).

## Live retraining (closing the sim-to-real gap)

```
deployed policy (sim-trained) ──ε-greedy──▶ experience on TRAIN scenarios (pinned dataset)
        │                                              │ aggregate rounds
        └──── warm start ────▶ offline Double DQN ◀────┘
                                    │ select snapshot on VAL scenarios
                                    ▼
                       candidate checkpoint (+ lineage manifest)
                                    │ evaluate ONCE on HOLDOUT (paired episodes)
                                    ▼
          promotion_report.json  ──▶  registry promote --approved-by usr_*  (human)
```

```sh
cd rl-defense
PYTHONPATH=.:../shared:../standards:../examples/payments-lite/target \
  .venv/bin/python -m rl_defense.live.pipeline --base-steps 30000 --rounds 3 \
  --out runs/live/retrain-v1 --evidence-dir results/live-retrain
# then, only if the report says recommend_promote and a human agrees (k = report candidate.round):
.venv/bin/python -m rl_defense.live.registry init --checkpoint runs/live/retrain-v1/base/ddqn_seed0.pt --approved-by usr_<you>
.venv/bin/python -m rl_defense.live.registry register --checkpoint runs/live/retrain-v1/candidate_round<k>.pt --report runs/live/retrain-v1/promotion_report.json
.venv/bin/python -m rl_defense.live.registry promote --version pol_<id> --approved-by usr_<you> --reason "..."
```

Discipline: the candidate only ever trains on **train** scenarios, snapshots and rounds are
chosen on **val**, and the **holdout** scenarios (unseen timing and intensity) are evaluated
once. Traffic for a (scenario, seed) is identical for every policy, so comparisons are paired.

**First result (v1):** the candidate beats the deployed sim-trained policy by +5.38
return [4.54, 6.35] and cuts compromise from 100% to 28%. The gate still **rejects** it:
live-tuned threshold rules score higher (−6.69 vs −7.98), and availability is 0.76 against
the 0.85 floor, which node-level isolation cannot reach while attacks are active about 45%
of the time. Holdout exposure during development is disclosed in [`PROVENANCE.md`](../../results/live-retrain/PROVENANCE.md).
The acceptance criteria in `configs/live/promotion.yaml` were committed before the held-out
run. Nothing updates the deployed policy automatically. Results: [`results/live-retrain/REPORT.md`](../../results/live-retrain/REPORT.md).

**Second result (v2, `block_principal`):** a live-only action space adds a principal-scoped
block (`actions.py`; contract proposal in `coordination/messages/20261019T043718Z-alan-to-srihith-adam-block-principal-action.md`).
It was judged on new, never-evaluated holdout scenarios (`configs/live/holdout_v2`: two
attacker identities, token rotation, outsider + insider). The candidate now clears the
availability floor (0.889) and gains +7.30 [6.27, 8.39] over the deployed policy. The gate
still **rejects** it: rules that may also block score −6.96 vs −7.29, because the candidate
adds `raise_monitoring` steps that cost reward and contain nothing.
See [`results/live-retrain-v2/REPORT.md`](../../results/live-retrain-v2/REPORT.md) and its
[`PROVENANCE.md`](../../results/live-retrain-v2/PROVENANCE.md).

```sh
.venv/bin/python -m rl_defense.live.pipeline --action-space live_v2 --holdout-dir holdout_v2 \
  --base-steps 30000 --rounds 3 --out runs/live/retrain-v2 --evidence-dir results/live-retrain-v2
```

**Third result (v3, long and targeted blocks, delegated reads):** scenarios gain bookkeepers
with legitimate cross-tenant read access, which the detector flags. Blanket blocking now
costs availability. Live action space v3 adds `block_principal_long` (23) and
`block_top_principal_long` (24) plus six detector features. The candidate abstains unless an
action beats noop by a val-selected `noop_margin`, the fix for v2's useless
`raise_monitoring` steps. The rules are tuned with every new control. The gate **rejects** the
candidate: −13.87 vs rules −10.98, and availability 0.797. On val the candidate beat the
rules by about 3, but that did not transfer to `holdout_v3`. No containing policy reaches
the 0.85 floor there.
See [`results/live-retrain-v3/REPORT.md`](../../results/live-retrain-v3/REPORT.md) and
[`PROVENANCE.md`](../../results/live-retrain-v3/PROVENANCE.md).

## What is real, and what is not

**Real:** the target app (a real FastAPI service, in-process over an ASGI transport — no
sockets), the BOLA it contains, every HTTP request/response, the enforcement of each
defensive action, the compromise/disruption counts, the reward, and the transitions.

**Detection uses instrumentation only.** The gateway flags a cross-tenant attempt when the
bearer token's principal differs from the requested object's owner, both read from the
owned app's own store. The traffic generator's `is_attack` label and per-window
`attack_active` ground truth are kept for metrics (compromise, false disruption) and never
reach an observation. The gateway's own blocking is not counted as an anomaly.

**Honest limits (RQ-005):**
- The sim-trained policy under-contains on real signals (a sim-to-real gap); live
  retraining is how this module addresses it — see the report for the measured result.
- The reward weights (`LoopConfig`: `c_impact=1.0`, `c_disrupt=0.5`) were fixed before
  retraining. They price availability low enough that blanket isolation of payments earns
  a competitive return while blocking about half of legitimate traffic; the gate's
  availability, false-disruption and duty checks exist precisely to reject that.
- One small demo app, one attack class (BOLA reads), a handful of fixture attacker
  identities, and a fixed five-node topology; generalization beyond these is untested.
- The route→node topology is the hand-written `configs/topology/payments_lite.yaml`.
- Numbers are lab evidence, not proof of real-world effectiveness.

## Tests

```sh
.venv/bin/python -m pytest -q tests/test_live_gateway.py tests/test_live_loop.py tests/test_live_retrain.py tests/test_live_block_principal.py tests/test_live_v3.py
```

`test_live_v3.py` proves that delegated reads are benign but flagged, and that blanket
blocking then costs availability with no attack at all. It proves that long blocks close the
identity-switch leak, that extensions never shorten a block, and that the top-target block
spares a delegate seen in the same window. It also covers the detector features, the strict
v2⊂v3 extension, exact widening, the noop margin, v3 rules using every control, holdout_v3
hygiene, and a v3 pipeline smoke test (on the exposed holdout_v2).

`test_live_block_principal.py` proves the block's real effect (403, no data, other tenants
unaffected, rotated tokens still blocked), its duration and masking in the loop, that it
beats isolation on availability under identical traffic, that widened sim agents act
exactly as before, that v2 checkpoints are refused by `PolicyRunner`, and the gate's
behavior on measured v2 episodes.

`test_live_gateway.py` proves each action's real effect and that telemetry is measured;
`test_live_loop.py` proves the full trained-DQN loop produces well-formed transitions,
never picks a masked action, really contains when it isolates, and that
`request_reassessment` really lowers the observed finding severity after its delay.
`test_live_retrain.py` proves transitions chain (s′ of one step is s of the next),
telemetry never reads the generator label, traffic is paired across policies, splits are
disjoint, datasets are train-only and tamper-evident, retraining selects on val only and
records lineage, the gate rejects blanket isolation, and the registry refuses agent
approvers, failing reports, mismatched bytes, and swapped checkpoints, and rolls back.

## Safety

Owned, isolated target only; in-process (no network egress); only the permitted defensive
actions are enforced; no path to any system outside the demo app. See docs/15.
