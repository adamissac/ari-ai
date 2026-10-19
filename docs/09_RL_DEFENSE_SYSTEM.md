# 09 — RL defense system

Status: **specified**. Directory: `rl-defense/`. Decision:
[ADR-0008](decisions/0008-offline-double-dqn.md). Evaluation:
[17](17_RL_EVALUATION_PROTOCOL.md). Deep dive:
[architecture/rl-training-and-inference](architecture/rl-training-and-inference.md).

## What it is — and is not

- **Is:** an offline reinforcement-learning agent trained in a *simulated*
  environment to choose defensive responses to evolving security signals, plus an
  inference service that turns a checkpoint into **recommendations** for humans.
- **Is not:** an autonomous responder. It never calls real infrastructure, never
  blocks traffic, never rotates real credentials. Every output is labeled
  "simulation-derived recommendation".

## Why RL at all (and the honest caveat)

Defensive response is sequential: acting too early disrupts users, acting too late
lets an attacker progress. RL is a natural fit for learning that trade-off. The
caveat: a policy is only as good as the simulator. Our claim is limited to
*"in our simulator, under protocol [17], the DDQN policy outperforms these
baselines by this much"*. Transfer to real systems is research question RQ-005.

## Environment: `DefenseSimEnv-v0` (Gymnasium)

A small service topology (default 5 nodes: gateway, api, auth, payments, db) with
an adversary that progresses through abstract stages. Adversary behavior is a
stochastic model of **stages**, not real techniques.

### Observation (vector, normalized to [0, 1])
| Feature group | Per node? | Examples |
|---|---|---|
| Alert signals | yes | alert rate (last 5 steps), anomaly score |
| Asset context | yes | criticality (from expectations/data sensitivity), exposed (bool) |
| Known risk | yes | open validated-finding severity max, patched (bool) |
| Defense state | yes | monitoring level, rate-limited, isolated |
| Global | no | time step / horizon, remaining action budget |

### Action space (discrete)
`noop`, and per node: `raise_monitoring`, `rate_limit`, `isolate`,
`request_reassessment`; plus global `escalate_to_human`. 5 nodes → 1 + 5×4 + 1 = 22
actions. All actions are *simulated* effects.

The live lab (`rl-defense/rl_defense/live/`) also has an action space v2: the same 22
actions plus global `block_principal` (index 22), which the gateway enforces against the
in-process demo app. `block_principal` is part of `shared.rl.DefenseActionName`, but no
simulator policy can choose it, and v2 checkpoints are not served as recommendations.

### Adversary model
Abstract stage progression per node: `none → foothold → escalated → impact`.
Transition probabilities depend on node exposure, open-finding severity, and
active defenses. Detection signals are noisy functions of stage plus benign
background noise. Scenario configs (YAML) set topology, noise and adversary
aggressiveness; train and held-out eval configs are separate.

### Reward
```
r_t = − c_impact · Σ impact(node)       # adversary reached impact stage
      − c_progress · Σ Δstage(node)      # adversary progressed this step
      − c_disrupt · Σ disruption(action) # isolation/rate-limit on benign nodes cost more
      − c_action · [action ≠ noop]
      + c_contain · Σ contained(node)    # adversary pushed back / blocked
```
Default coefficients live in the config and are part of the experiment record.
Reward shaping changes require a new env version (`-v1`), never silent edits.

### Episode
Horizon 200 steps; terminates early if `impact` on the `db` node.

## Agent: Double DQN

- PyTorch MLP Q-network (2×128, ReLU), target network with soft update (τ = 0.005)
  or hard update every 1,000 steps (config).
- Double DQN target: action chosen by online net, valued by target net.
- Replay buffer 100k, batch 64, γ = 0.99, Adam lr 1e-3, ε-greedy 1.0 → 0.05 over
  50k steps, Huber loss, gradient clip 10.
- These are starting hyperparameters, not tuned results.

## Baselines (mandatory in every comparison)
1. `random` — uniform over actions.
2. `noop` — never acts.
3. `threshold_rules` — hand-written: isolate a node when anomaly > θ₁ and
   criticality high; rate-limit when alert rate > θ₂; escalate when two nodes
   exceed θ₁. Thresholds tuned on *training* configs only.

## Connection to the rest of the platform
- **Inputs from P1/P2:** node criticality from expectation data-sensitivity tags;
  open-finding severity from validated findings. In the MVP these are mapped onto
  the simulator's demo topology by a hand-written config, not live.
- **Inputs from P3:** monitoring signals can be replayed as observation
  sequences for offline evaluation (stretch).
- **Outputs:** `DefenseRecommendation{action, node, q_value_margin, policy_version,
  observation_snapshot, caveat}` shown in the UI's monitoring panel.

## Artifacts
Checkpoints (`*.pt`) and run logs go to `rl-defense/runs/` locally (git-ignored)
and the artifact store later. Every checkpoint has a manifest: env version,
config hash, seed, git SHA, training steps, eval summary path.
