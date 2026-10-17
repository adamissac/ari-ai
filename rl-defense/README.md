# rl-defense/

> **Implemented (simulation only).** A Gymnasium environment, a trained Double DQN,
> three baselines, a protocol-compliant evaluation, and an inference adapter that
> produces *recommendations*. Nothing here acts on a real system.
> Specs: [docs/09](../docs/09_RL_DEFENSE_SYSTEM.md), [docs/17](../docs/17_RL_EVALUATION_PROTOCOL.md),
> [architecture/rl-training-and-inference](../docs/architecture/rl-training-and-inference.md).
> Owner: Adam ([coordination/OWNERSHIP](../coordination/OWNERSHIP.md)).

## What exists

| Piece | Module | Status |
|---|---|---|
| `DefenseSimEnv-v0` (Gymnasium, registered) | `rl_defense/envs/defense_sim.py` | ✅ passes `check_env`; seeded-deterministic; hidden-state leakage test |
| Scenario configs (3 train, 3 held-out eval) | `configs/train/`, `configs/eval/` | ✅ hashed; reward coefficients identical across all |
| Double DQN (online/target nets, masked replay, ε-greedy, Huber, grad clip, hard/soft sync) | `rl_defense/agents/ddqn.py` | ✅ target-math unit tests |
| Baselines: `noop`, `random` (valid actions), `threshold_rules` (tuned on train configs only) | `rl_defense/baselines/` | ✅ |
| Training CLI with checkpoint + manifest (sha256, git SHA, configs, seed) | `rl_defense/train.py`, `rl_defense/checkpoint.py` | ✅ |
| Protocol-17 evaluation (5 seeds × 100 episodes × held-out configs, bootstrap CIs, Welch + Holm) | `rl_defense/evaluate.py` | ✅ |
| Inference → typed `DefenseRecommendation` (`simulation_derived=true`, caveat) | `rl_defense/inference.py`, `rl_defense/contracts.py` | ✅ re-exports canonical `shared.rl` (V0) |
| Platform facts → observation mapping | `rl_defense/observations.py` | ✅ (hand-written topology mapping; see limits) |
| Public API for other subsystems | `rl_defense/api.py` | ✅ |
| Recommendation explanations (occlusion) | `rl_defense/explain.py` | ✅ exact-value tests |
| Platform records → policy inputs (findings, expectations, signals) | `rl_defense/platform_mapping.py` | ✅ |
| Failure analysis, stress test, Defense Lab export | `analysis.py`, `stress.py`, `lab_export.py` | ✅ |
| Reference evaluation results | [`results/protocol-v1/`](results/protocol-v1/COMPARISON.md) (current), [`results/protocol-v0/`](results/protocol-v0/eval_table.md) | ✅ real output, see below |
| Backend endpoint / UI panel | backend (Srihith), frontend (Vihaan) | ❌ not integrated yet |

## The environment in one paragraph

Five nodes (gateway, api, auth, payments, db) with criticality, exposure and open
finding severity. A hidden adversary moves each node through abstract stages
`none → foothold → escalated → impact`, entering via exposed nodes and spreading
along edges; open findings speed it up. The defender sees only noisy alert rates
and anomaly scores plus asset context (48 features: 9 per node + 3 global) and picks one of 22 actions:
`noop`; per node `raise_monitoring`, `rate_limit`, `isolate`,
`request_reassessment`; or `escalate_to_human` (budget of 3). Invalid actions are
masked. Reward penalizes impact, adversary progress, disruption (more on benign
nodes), action and escalation cost, and rewards containment. Losing the db ends the
episode and charges the remaining horizon's impact cost, so dying early is never
cheaper than defending.

**Metric definitions** follow docs/17, with one clarification: *time to containment*
is the steps from the first foothold until all nodes are back to `none` for 10
consecutive steps (censored at the horizon); episodes where the adversary never got
in are excluded.

## Current policy: protocol-v1

**Use `runs/protocol-v1/ddqn_seed0.pt`** (reproduce with `python -m experiments.final`; manifests,
eval summary and comparison in [`results/protocol-v1/`](results/protocol-v1/COMPARISON.md)).
It was selected on a validation protocol (training configs, validation seeds 10–14 and 2000–2099)
and evaluated **once** on the held-out configs, seeds 0–4 × 1000–1099. Settings: lr 3e-4,
1M steps, 3-step returns, attacker-speed randomization ×0.5–2.5, in-training checkpoint
selection. Details: [`experiments/README.md`](experiments/README.md). An independent audit
recomputed return, compromise and db loss from the raw episodes and got the same numbers.

| Policy | Return | Compromise % | db lost % | False disruption % | Uptime % |
|---|---|---|---|---|---|
| **DDQN protocol-v1** | **−29.1** [−32.1, −26.1] | **7.1** [4.1, 11.2] | 1.1 | 75.0 [69.6, 79.8] | 94.4 |
| DDQN protocol-v0 | −65.6 [−72.1, −59.7] | 47.5 | 9.8 | 53.9 | 93.8 |
| threshold_rules | −96.0 | 83.0 | 0.3 | 28.7 | 93.3 |

- v1 beats v0 and every baseline on return. In the stress test it also beats the rules at
  every attacker speed up to ×2.5 (v0 lost at ×2.5); db loss at ×2.5 is 11.6% (rules 10%).
- **Regression:** false disruption rose to 75%, meaning most of its rate-limits and
  isolations hit nodes that weren't compromised yet. It's preventive, and cheap in uptime
  terms (94.4%), but a human should know.
- *Results are from a simulated environment and do not establish real-world effectiveness.*

## Earlier results (protocol v0, commit `1182773`)

Full table: [`results/protocol-v0/eval_table.md`](results/protocol-v0/eval_table.md);
machine-readable: [`eval_summary.json`](results/protocol-v0/eval_summary.json). Held-out
eval configs only, 5 training seeds × 100 episodes × 3 configs, 200k steps per seed.
A clean retrain from the commit reproduced identical per-seed metrics.

| Policy | Return | Compromise % | False disruption % | Uptime % |
|---|---|---|---|---|
| **ddqn** | **−65.6** [−72.1, −59.7] | 47.5 [35.3, 58.9] | 53.9 [45.8, 63.1] | 93.8 |
| threshold_rules | −96.0 | 83.0 | 28.7 | 93.3 |
| random (valid actions) | −154.3 [−155.1, −153.4] | 8.9 [7.7, 10.0] | 94.3 | 41.2 |
| noop | −386.2 | 100.0 | n/a | 100.0 |

What this shows, and does not show:
- DDQN gets the best return on all three held-out configs and significantly beats every
  baseline on return (Holm-corrected).
- Against the tuned rules it cuts compromise from 83% to 47.5% and contains faster,
  **but it disrupts benign nodes more often** (54% vs 29% false disruption).
- `random` is compromised far less (8.9%) only because it constantly isolates nodes:
  uptime drops to 41%. DDQN is **worse than random on compromise rate**.
- **DDQN loses the db node in 9.8% of episodes; the threshold rules in 0.3%.** The rules
  sacrifice gateway/api (~65% impact) to protect critical nodes; DDQN spreads protection
  more evenly. DDQN's worst episodes are all fast attacks in the aggressive scenario
  (foothold at step 0–1, impact by step 6). See
  [`results/protocol-v0/ANALYSIS.md`](results/protocol-v0/ANALYSIS.md) for reward
  breakdowns, per-node impact, action mix, per-seed variation (compromise 25–63%) and
  deterministic replays of the worst episodes.
- **It does not generalize to faster attackers.** In the stress sweep
  ([`stress_table.md`](results/protocol-v0/stress_table.md)), every adversary probability
  is scaled ×0.5–×2.5. DDQN leads on return up to ×1.5, ties the rules at ×2 and is worse
  at ×2.5, and its db-loss rate rises to 61% (rules: 10%). Training with
  aggressiveness randomization is the next experiment.
- CIs are across 5 seeds; deterministic baselines have zero seed variance.
- *Results are from a simulated environment and do not establish real-world effectiveness.*

## Commands

```bash
cd rl-defense
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -e ../standards -e ../shared -e ".[dev]"  # same as .github/workflows/rl.yml

.venv/bin/python -m pytest -q                       # all tests (~1 min)
.venv/bin/ruff check rl_defense tests && .venv/bin/ruff format --check rl_defense tests

# Full protocol (≈75 s per seed on CPU; seeds run in parallel)
for s in 0 1 2 3 4; do .venv/bin/python -m rl_defense.train --seed $s --steps 200000 --run-dir runs/protocol-v0 & done; wait
.venv/bin/python -m rl_defense.evaluate --run-dir runs/protocol-v0
.venv/bin/python -m rl_defense.analysis --run-dir runs/protocol-v0   # failure cases + breakdowns
.venv/bin/python -m rl_defense.stress --run-dir runs/protocol-v0     # aggressiveness sweep (~4 min)
.venv/bin/python -m rl_defense.lab_export --run-dir runs/protocol-v0 --out lab.json --schema lab.schema.json
```

`runs/` (checkpoints, logs, raw episodes) is git-ignored. Reference copies of the
summary, table and a few trajectories are committed under `results/`.

## Using it from the backend

```python
from rl_defense.api import load_policy
from rl_defense.platform_mapping import (
    FindingInput, ExpectationInput, RouteSignal, facts_from_platform, load_topology,
)

topology = load_topology("configs/topology/payments_lite.yaml")   # route -> node mapping
facts, provenance = facts_from_platform(
    topology,
    findings=[FindingInput(id="fnd_…", status="validated", severity="high",
                           routes=("GET /payments/{payment_id}",))],
    expectations=[ExpectationInput(id="exp_…", route="GET /payments/{payment_id}",
                                   data_sensitivity="financial", status="confirmed")],
    signals=[RouteSignal(route="GET /payments/{payment_id}", alert_rate=4.0,
                         anomaly_score=0.4, source="runtime_demo")],
)
runner = load_policy("runs/protocol-v1/ddqn_seed0.pt")  # verifies sha256 against the manifest
rec = runner.recommend(facts)                           # -> DefenseRecommendation
```

`runner.recommend_with_explanation(facts)` also returns an `RLExplanation` (shared V0.1)
listing which observed inputs drove the choice (occlusion
analysis on the same Q-network): each input is set to zero and the change in the
chosen action's margin over the runner-up is measured. When inputs move the margin far
more than the margin itself, the decision is low-confidence, and the UI should say so.
Example output is in the same fixture file.

Only validated, still-open findings raise a node's risk input. Hypotheses, refuted
findings and verified fixes don't, so a fix verified by the Verify agent changes the
next recommendation. `provenance` records which finding, expectation and signal ids
drove each node's inputs, so the UI can link a recommendation back to evidence.

Example payload: [`fixtures/defense_recommendation.example.json`](fixtures/defense_recommendation.example.json).

## Limits (read before presenting results)

- Every number comes from **simulation**. Nothing here shows real-world detection or
  response ability (RQ-005).
- The adversary is an abstract stage model, not a model of real techniques.
- Mapping a real project onto the 5-node topology is a hand-written config, and
  real alert signals are not calibrated to the simulator's noise model.
- There is no code path from a recommendation to any action.

### Standards classifications

Producer standards fields resolve through the pinned offline `standards` catalog.
CWE proposals must identify real, nondeprecated weaknesses (categories such as
CWE-840 are not accepted as weakness classifications). CWE/CAPEC/ATT&CK catalog relationships are review candidates; they are not
automatically attached as ATT&CK mappings. These are
classifications, not evidence of production adversary activity.

Canonical `standards.mapping` validates classifications and reviewed rules.
CVSS is separate from the existing qualitative severity rubric. Trace can accept
a complete set of explicit CVSS v4 base metrics with executed validation artifact
references, then computes and validates the vector and score deterministically.
Missing metrics or unrelated artifacts leave the finding unscored. Evidence
provenance does not by itself prove an analyst's metric interpretation.

D3FEND mappings use the owner-reviewed rules keyed by Fortify category and
confirmed check category. Unsupported combinations remain unmapped. Reviewed RL actions have simulation-derived D3FEND
classifications, while unsupported actions stay unmapped. No rule
executes a defensive action against real systems.
