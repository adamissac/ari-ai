"""Train a Double DQN policy on DefenseSimEnv training configs.

    python -m rl_defense.train --seed 0 --steps 200000 --run-dir runs/<run_id>

Each episode samples one training config uniformly. Held-out eval configs are
never loaded here.
"""

from __future__ import annotations

import argparse
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


def set_determinism(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)


def train(
    configs: list[ScenarioConfig],
    seed: int,
    steps: int,
    run_dir: Path,
    ddqn_config: DDQNConfig | None = None,
    log_every: int = 5_000,
) -> dict:
    if any(c.split != "train" for c in configs):
        raise ValueError("training must only use configs with split=train")
    set_determinism(seed)
    cfg = ddqn_config or DDQNConfig()
    run_dir.mkdir(parents=True, exist_ok=True)
    envs = [DefenseSimEnv(c) for c in configs]
    rng = np.random.default_rng(seed)
    agent = DDQNAgent(OBS_DIM, N_ACTIONS, cfg, seed=seed)
    buffer = ReplayBuffer(cfg.buffer_size, OBS_DIM, N_ACTIONS, seed=seed)
    nstep = NStepAccumulator(cfg.n_step, cfg.gamma) if cfg.n_step > 1 else None
    initial_params = [p.detach().clone() for p in agent.online.parameters()]

    log_path = run_dir / f"train_seed{seed}.jsonl"
    log = log_path.open("w")
    episode, ep_return, ep_len = 0, 0.0, 0
    env = envs[rng.integers(len(envs))]
    obs, info = env.reset(seed=int(rng.integers(2**31)))
    recent_returns: list[float] = []
    last_stats: dict[str, float] = {}
    start = time.time()

    for step in range(1, steps + 1):
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
            env = envs[rng.integers(len(envs))]
            obs, info = env.reset(seed=int(rng.integers(2**31)))
            ep_return, ep_len = 0.0, 0

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
            "gradient_updates": agent.updates,
            "param_abs_change": param_change,
            "wall_clock_s": round(time.time() - start, 1),
            "train_log": log_path.name,
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
    args = ap.parse_args()
    configs = load_configs(args.config or default_config_paths("train"))
    ddqn = DDQNConfig(**yaml.safe_load(args.ddqn_config.read_text())) if args.ddqn_config else None
    manifest = train(configs, args.seed, args.steps, args.run_dir, ddqn, args.log_every)
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
