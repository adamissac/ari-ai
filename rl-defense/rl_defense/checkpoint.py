"""Checkpoint save/load with a manifest (docs/09 §Artifacts)."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import torch

from rl_defense import ENV_ID
from rl_defense.agents.ddqn import DDQNAgent, DDQNConfig
from rl_defense.envs.defense_sim import N_ACTIONS, OBS_DIM


def git_sha() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def save_checkpoint(
    agent: DDQNAgent,
    path: Path,
    *,
    seed: int,
    steps: int,
    train_configs: dict[str, str],
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "env_id": ENV_ID,
        "obs_dim": OBS_DIM,
        "n_actions": N_ACTIONS,
        "seed": seed,
        "steps": steps,
        "train_configs": train_configs,  # name -> config hash
        "ddqn_config": agent.config.model_dump(mode="json"),
        "git_sha": git_sha(),
        "created_at": datetime.now(UTC).isoformat(),
        **(extra or {}),
    }
    torch.save({"agent": agent.state_dict(), "manifest": manifest}, path)
    manifest["checkpoint_file"] = path.name
    manifest["checkpoint_sha256"] = sha256_file(path)
    path.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def load_checkpoint(path: Path, verify: bool = True) -> tuple[DDQNAgent, dict[str, Any]]:
    path = Path(path)
    manifest_path = path.with_suffix(".manifest.json")
    if verify and manifest_path.exists():
        expected = json.loads(manifest_path.read_text())["checkpoint_sha256"]
        actual = sha256_file(path)
        if actual != expected:
            raise ValueError(f"checkpoint hash mismatch for {path}: {actual} != {expected}")
    blob = torch.load(path, map_location="cpu", weights_only=False)
    manifest = blob["manifest"]
    if manifest["env_id"] != ENV_ID or manifest["obs_dim"] != OBS_DIM:
        raise ValueError(
            f"checkpoint was trained for {manifest['env_id']} obs_dim={manifest['obs_dim']}"
        )
    agent = DDQNAgent(
        OBS_DIM, N_ACTIONS, DDQNConfig(**manifest["ddqn_config"]), seed=manifest["seed"]
    )
    agent.load_state_dict(blob["agent"])
    agent.online.eval()
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
    return agent, manifest
