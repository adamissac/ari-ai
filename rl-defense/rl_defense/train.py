"""Train a Double DQN policy on DefenseSimEnv training configs.

    python -m rl_defense.train --seed 0 --steps 200000 --run-dir runs/<run_id>

Each episode samples one training config uniformly. Held-out eval configs are
never loaded here. With ``--adversary-scale LOW HIGH`` (domain randomization), each
episode also samples a factor uniformly in [LOW, HIGH] and multiplies the sampled
training config's adversary transition probabilities by it (capped at 1.0). Without
it, the random-draw sequence is identical to protocol-v0, so v0 runs stay reproducible.
"""

from __future__ import annotations

import argparse
import copy
import json
import random
import time
from pathlib import Path

import numpy as np
import torch
import yaml

from rl_defense.agents.ddqn import DDQNAgent, DDQNConfig, NStepAccumulator, ReplayBuffer
from rl_defense.checkpoint import save_checkpoint
from rl_defense.envs import DefenseSimEnv, default_config_paths, load_configs
from rl_defense.envs.config import ScenarioConfig
from rl_defense.envs.defense_sim import N_ACTIONS, OBS_DIM
from rl_defense.evaluate import run_episode
from rl_defense.stress import scaled


def set_determinism(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)


CKPT_SELECT_SEEDS = range(
    5000, 5030
)  # disjoint from eval 1000-1099, validation 2000-2099, stress 3000-3049
CKPT_SELECT_FACTORS = (1.0, 2.0)


class _GreedyPolicy:
    """Greedy masked policy that does not consume the agent's exploration RNG."""

    name = "ddqn_greedy"

    def __init__(self, agent: DDQNAgent) -> None:
        self.agent = agent

    def reset(self, seed: int) -> None:
        pass

    def act(self, obs: np.ndarray, mask: np.ndarray) -> int:
        return self.agent.greedy_action(obs, mask)


def selection_score(
    agent: DDQNAgent, configs: list[ScenarioConfig], fd_penalty: float = 0.0
) -> float:
    """Mean greedy return on TRAINING configs at CKPT_SELECT_FACTORS (never eval configs),
    minus ``fd_penalty`` × mean false-disruption rate in percentage points (0 = return only).
    Episodes without disruptive actions count as 0% false disruption."""
    assert all(c.split == "train" for c in configs)
    policy = _GreedyPolicy(agent)
    returns, fds = [], []
    for base in configs:
        for factor in CKPT_SELECT_FACTORS:
            env = DefenseSimEnv(base if factor == 1.0 else scaled(base, factor))
            for s in CKPT_SELECT_SEEDS:
                row = run_episode(env, policy, s)[0]
                returns.append(row["return"])
                fd = row["false_disruption_rate"]
                fds.append(0.0 if fd != fd else fd)  # NaN -> 0
    return float(np.mean(returns)) - fd_penalty * 100.0 * float(np.mean(fds))


def train(
    configs: list[ScenarioConfig],
    seed: int,
    steps: int,
    run_dir: Path,
    ddqn_config: DDQNConfig | None = None,
    log_every: int = 5_000,
    adversary_scale: tuple[float, float] | None = None,
    select_every: int | None = None,
    select_start: int = 0,
    select_fd_penalty: float = 0.0,
) -> dict:
    """Train one seed. ``select_every`` enables in-training checkpoint selection: every
    ``select_every`` steps after ``select_start`` the greedy policy is scored on the
    TRAINING configs (factors ``CKPT_SELECT_FACTORS``, episode seeds ``CKPT_SELECT_SEEDS``)
    and the best-scoring weights are the ones saved."""
    if any(c.split != "train" for c in configs):
        raise ValueError("training must only use configs with split=train")
    if adversary_scale is not None and not 0.0 < adversary_scale[0] <= adversary_scale[1]:
        raise ValueError(f"adversary_scale must satisfy 0 < low <= high, got {adversary_scale}")
    if select_every is not None and select_every < 1:
        raise ValueError("select_every must be >= 1")
    set_determinism(seed)
    cfg = ddqn_config or DDQNConfig()
    run_dir.mkdir(parents=True, exist_ok=True)
    envs = [DefenseSimEnv(c) for c in configs]
    rng = np.random.default_rng(seed)
    factors: list[float] = []

    def next_env() -> DefenseSimEnv:
        base = int(rng.integers(len(envs)))
        if adversary_scale is None:
            return envs[base]
        factor = float(rng.uniform(*adversary_scale))
        factors.append(factor)
        return DefenseSimEnv(scaled(configs[base], factor))

    # disruption_margin is a deployment-time rule: training behaviour and in-training
    # checkpoint selection use the plain masked argmax; the margin is saved with the
    # checkpoint and applies to greedy evaluation and recommendations.
    agent = DDQNAgent(
        OBS_DIM, N_ACTIONS, cfg.model_copy(update={"disruption_margin": 0.0}), seed=seed
    )
    buffer = ReplayBuffer(cfg.buffer_size, OBS_DIM, N_ACTIONS, seed=seed)
    nstep = NStepAccumulator(cfg.n_step, cfg.gamma) if cfg.n_step > 1 else None
    initial_params = [p.detach().clone() for p in agent.online.parameters()]

    log_path = run_dir / f"train_seed{seed}.jsonl"
    log = log_path.open("w")
    episode, ep_return, ep_len = 0, 0.0, 0
    env = next_env()
    obs, info = env.reset(seed=int(rng.integers(2**31)))
    recent_returns: list[float] = []
    last_stats: dict[str, float] = {}
    selection_history: list[dict[str, float]] = []
    best: tuple[float, int, dict] | None = None
    start = time.time()

    for step in range(1, steps + 1):
        if cfg.lr_end is not None:
            lr = cfg.lr + (cfg.lr_end - cfg.lr) * min(1.0, step / steps)
            for group in agent.optimizer.param_groups:
                group["lr"] = lr
        eps = agent.epsilon(step)
        action = agent.act(obs, info["action_mask"], eps)
        next_obs, reward, terminated, truncated, info = env.step(action)
        # Bootstrap through truncation (time limit); only true termination stops the target.
        if nstep is None:
            buffer.add(obs, action, reward, next_obs, terminated, info["action_mask"])
        else:
            for tr in nstep.push(
                obs, action, reward, next_obs, terminated, truncated, info["action_mask"]
            ):
                buffer.add(*tr)
        obs = next_obs
        ep_return += reward
        ep_len += 1

        if step > cfg.learning_starts and step % cfg.train_freq == 0:
            last_stats = agent.update(buffer.sample(cfg.batch_size))

        if terminated or truncated:
            recent_returns.append(ep_return)
            episode += 1
            env = next_env()
            obs, info = env.reset(seed=int(rng.integers(2**31)))
            ep_return, ep_len = 0.0, 0

        if select_every and step >= select_start and (step % select_every == 0 or step == steps):
            score = selection_score(agent, configs, select_fd_penalty)
            selection_history.append({"step": step, "score": score})
            if best is None or score > best[0]:
                best = (score, step, copy.deepcopy(agent.state_dict()))

        if step % log_every == 0 or step == steps:
            row = {
                "step": step,
                "episodes": episode,
                "epsilon": round(eps, 4),
                "mean_return_last20": float(np.mean(recent_returns[-20:]))
                if recent_returns
                else None,
                "updates": agent.updates,
                "elapsed_s": round(time.time() - start, 1),
                **last_stats,
            }
            log.write(json.dumps(row) + "\n")
            log.flush()
    log.close()

    final_step_updates = agent.updates
    agent.config = cfg  # restore the deployment margin before saving
    if best is not None:
        agent.load_state_dict(best[2])
    param_change = float(
        sum(
            (p.detach() - p0).abs().sum()
            for p, p0 in zip(agent.online.parameters(), initial_params, strict=True)
        )
    )
    manifest = save_checkpoint(
        agent,
        run_dir / f"ddqn_seed{seed}.pt",
        seed=seed,
        steps=steps,
        train_configs={c.name: c.config_hash() for c in configs},
        extra={
            "episodes": episode,
            "gradient_updates": final_step_updates,
            "checkpoint_selection": {
                "every": select_every,
                "start": select_start,
                "episode_seeds": [CKPT_SELECT_SEEDS.start, CKPT_SELECT_SEEDS.stop - 1],
                "factors": list(CKPT_SELECT_FACTORS),
                "fd_penalty": select_fd_penalty,
                "selected_step": best[1],
                "selected_score": best[0],
                "updates_at_selected_step": agent.updates,
                "history": selection_history,
            }
            if best is not None
            else None,
            "param_abs_change": param_change,
            "wall_clock_s": round(time.time() - start, 1),
            "train_log": log_path.name,
            "adversary_scale": list(adversary_scale) if adversary_scale else None,
            "adversary_scale_sampled": {
                "min": min(factors),
                "mean": float(np.mean(factors)),
                "max": max(factors),
            }
            if factors
            else None,
        },
    )
    return manifest


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--steps", type=int, default=200_000)
    ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument(
        "--config",
        type=Path,
        action="append",
        help="training config(s); default: configs/train/*.yaml",
    )
    ap.add_argument("--ddqn-config", type=Path, help="YAML of DDQNConfig overrides")
    ap.add_argument("--log-every", type=int, default=5_000)
    ap.add_argument(
        "--adversary-scale",
        type=float,
        nargs=2,
        metavar=("LOW", "HIGH"),
        help="domain randomization: per-episode adversary probability factor ~ U[LOW, HIGH]",
    )
    ap.add_argument("--select-every", type=int, help="in-training checkpoint selection interval")
    ap.add_argument("--select-start", type=int, default=0)
    ap.add_argument(
        "--select-fd-penalty",
        type=float,
        default=0.0,
        help="checkpoint selection: subtract this × false-disruption percentage points",
    )
    args = ap.parse_args()
    configs = load_configs(args.config or default_config_paths("train"))
    ddqn = DDQNConfig(**yaml.safe_load(args.ddqn_config.read_text())) if args.ddqn_config else None
    scale = tuple(args.adversary_scale) if args.adversary_scale else None
    manifest = train(
        configs,
        args.seed,
        args.steps,
        args.run_dir,
        ddqn,
        args.log_every,
        scale,
        select_every=args.select_every,
        select_start=args.select_start,
        select_fd_penalty=args.select_fd_penalty,
    )
    print(
        json.dumps(
            {
                k: manifest[k]
                for k in (
                    "seed",
                    "steps",
                    "episodes",
                    "gradient_updates",
                    "param_abs_change",
                    "wall_clock_s",
                    "checkpoint_file",
                    "checkpoint_sha256",
                )
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
