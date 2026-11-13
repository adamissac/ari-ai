"""Run one simulated defense episode on request and return every decision, fully traceable.

    python -m rl_defense.lab_episode --scenario eval_aggressive_noisy --policy ddqn_trained --seed 1000

This is what an interactive lab plays back: for each step, the observation the policy saw,
the valid actions, the Q-values the network produced (learned policies only), the action
taken, the reward with its named components, and the simulator's ground truth. Nothing is
recorded in advance; the episode is computed when asked, from a hash-pinned checkpoint.

Policies:

- ``ddqn_trained``   : the committed checkpoint (sha256-verified), greedy
- ``ddqn_untrained`` : the same architecture and init seed with zero gradient updates
- ``random``         : uniform over valid actions
- ``noop``           : never acts
- ``threshold_rules``: the hand-written rules, with the thresholds tuned on the training
  configs in the committed evaluation (never re-tuned here)

Everything runs in ``DefenseSimEnv``. No action reaches a real system.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from rl_defense import ENV_ID
from rl_defense.agents.ddqn import DDQNAgent, DDQNConfig
from rl_defense.baselines import (
    NoopPolicy,
    RandomValidPolicy,
    ThresholdParams,
    ThresholdRulesPolicy,
)
from rl_defense.checkpoint import load_checkpoint
from rl_defense.envs import DefenseSimEnv, default_config_paths, load_configs
from rl_defense.envs.config import NODE_NAMES, ScenarioConfig
from rl_defense.envs.defense_sim import (
    GLOBAL_FEATURES,
    N_ACTIONS,
    NODE_FEATURES,
    OBS_DIM,
    REWARD_COMPONENTS,
    action_label,
)
from rl_defense.evaluate import CAVEAT

LAB_EPISODE_SCHEMA_VERSION = "0.1.0"
RESULTS = Path(__file__).resolve().parents[1] / "results" / "protocol-v1-retrain"
DEFAULT_CHECKPOINT = RESULTS / "checkpoints" / "ddqn_seed0.pt"
DEFAULT_CHECKPOINT_SHA256 = "666145e00d4ee3b9a1839179d9d9aca5a245c20fe7a173e2cb960e34e0393fe8"
EVAL_SUMMARY = RESULTS / "eval_summary.json"
# The thresholds the committed protocol-v1-retrain evaluation tuned on the training configs
# (EVAL_SUMMARY["threshold_rules"]["params"]; equality is asserted in tests). Kept in code so
# an installed package without the results directory runs the same rules.
COMMITTED_THRESHOLD_PARAMS = ThresholdParams(
    isolate_anomaly=0.25, rate_limit_alerts=0.2, monitor_anomaly=0.1, criticality_min=0.6
)
STAGE_NAMES = ("none", "foothold", "escalated", "impact")
FEATURE_NAMES: tuple[str, ...] = (
    *(f"{node}.{feat}" for node in NODE_NAMES for feat in NODE_FEATURES),
    *GLOBAL_FEATURES,
)
ACTION_LABELS: tuple[str, ...] = tuple(action_label(a) for a in range(N_ACTIONS))
MAX_EPISODE_SEED = 2**31 - 1

PolicyKind = Literal["ddqn_trained", "ddqn_untrained", "random", "noop", "threshold_rules"]
POLICY_KINDS: tuple[PolicyKind, ...] = (
    "ddqn_trained",
    "ddqn_untrained",
    "random",
    "noop",
    "threshold_rules",
)
PolicySource = Literal["learned_checkpoint", "untrained_network", "scripted_baseline"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LabEpisodeNode(_Strict):
    name: str
    criticality: float
    exposed: bool
    finding_severity: float


class LabEpisodeScenario(_Strict):
    name: str
    split: Literal["train", "eval"]
    config_hash: str
    horizon: int
    nodes: list[LabEpisodeNode]
    edges: list[tuple[str, str]]


class LabEpisodePolicy(_Strict):
    kind: PolicyKind
    source: PolicySource
    description: str
    policy_version: str | None = Field(
        description="env id + checkpoint sha256 prefix; learned only"
    )
    checkpoint_sha256: str | None
    training_steps: int | None
    gradient_updates: int = Field(description="0 for the untrained network and the baselines")
    training_seed: int | None


class LabEpisodeStep(_Strict):
    t: int
    observation: list[float] = Field(description="what the policy saw before acting")
    action_mask: list[bool]
    q_values: list[float] | None = Field(
        description="network output for this observation; null for scripted baselines"
    )
    action: int
    action_label: str
    reward: float
    reward_components: dict[str, float]
    terminated: bool
    truncated: bool
    ground_truth_stages: list[str] = Field(
        description="hidden adversary stage per node after this step; never seen by the policy"
    )


class LabEpisodeSummary(_Strict):
    total_return: float
    steps: int
    terminated: bool = Field(description="db node lost before the horizon")
    ever_impact: bool
    impact_nodes: list[str]
    first_foothold_t: int | None
    containment_t: int | None
    action_counts: dict[str, int]


class LabEpisode(_Strict):
    schema_version: Literal["0.1.0"] = LAB_EPISODE_SCHEMA_VERSION
    kind: Literal["simulation"] = "simulation"
    caveat: str = CAVEAT
    env_id: str = ENV_ID
    episode_seed: int
    scenario: LabEpisodeScenario
    policy: LabEpisodePolicy
    feature_names: list[str]
    action_labels: list[str]
    reward_component_names: list[str]
    steps: list[LabEpisodeStep]
    final_observation: list[float]
    summary: LabEpisodeSummary


def scenarios(config_dir: Path | None = None) -> dict[str, ScenarioConfig]:
    """Every committed scenario config, by name. ``config_dir`` is the ``configs`` directory
    when the package is installed away from its source tree (the backend image)."""
    paths = [
        p
        for split in ("train", "eval")
        for p in (
            default_config_paths(split)
            if config_dir is None
            else sorted((config_dir / split).glob("*.yaml"))
        )
    ]
    return {c.name: c for c in load_configs(paths)}


def _load_trained(checkpoint: Path, expected_sha256: str | None) -> tuple[DDQNAgent, dict]:
    blob = Path(checkpoint).read_bytes()
    digest = hashlib.sha256(blob).hexdigest()
    if expected_sha256 is not None and digest != expected_sha256:
        raise ValueError(f"checkpoint hash mismatch for {checkpoint}: refusing to load")
    agent, manifest = load_checkpoint(checkpoint, blob=blob)
    if manifest["env_id"] != ENV_ID:
        raise ValueError(f"the lab simulator needs a {ENV_ID} checkpoint, got {manifest['env_id']}")
    return agent, {**manifest, "checkpoint_sha256": digest}


class _Policy:
    """A policy plus the provenance the UI must show next to its decisions."""

    def __init__(self, kind: PolicyKind, checkpoint: Path, expected_sha256: str | None) -> None:
        self.kind = kind
        self.agent: DDQNAgent | None = None
        self._scripted = None
        if kind in ("ddqn_trained", "ddqn_untrained"):
            trained, manifest = _load_trained(checkpoint, expected_sha256)
            if kind == "ddqn_trained":
                self.agent = trained
                self.info = LabEpisodePolicy(
                    kind=kind,
                    source="learned_checkpoint",
                    description="Double DQN, greedy, from the committed hash-pinned checkpoint",
                    policy_version=f"{ENV_ID}@{manifest['checkpoint_sha256'][:12]}",
                    checkpoint_sha256=manifest["checkpoint_sha256"],
                    training_steps=manifest["steps"],
                    gradient_updates=trained.updates,
                    training_seed=manifest["seed"],
                )
            else:
                # the trained checkpoint's own architecture and init seed, never updated
                self.agent = DDQNAgent(
                    OBS_DIM, N_ACTIONS, DDQNConfig(**manifest["ddqn_config"]), seed=manifest["seed"]
                )
                self.info = LabEpisodePolicy(
                    kind=kind,
                    source="untrained_network",
                    description="The same network at initialization: zero gradient updates",
                    policy_version=None,
                    checkpoint_sha256=None,
                    training_steps=0,
                    gradient_updates=0,
                    training_seed=manifest["seed"],
                )
            return
        if kind == "random":
            self._scripted = RandomValidPolicy(seed=0)
            description = "Uniformly random over the valid actions"
        elif kind == "noop":
            self._scripted = NoopPolicy()
            description = "Never acts"
        elif kind == "threshold_rules":
            self._scripted = ThresholdRulesPolicy(COMMITTED_THRESHOLD_PARAMS)
            description = "Hand-written threshold rules, tuned on the training configs"
        else:
            raise ValueError(f"unknown policy kind: {kind}")
        self.info = LabEpisodePolicy(
            kind=kind,
            source="scripted_baseline",
            description=description,
            policy_version=None,
            checkpoint_sha256=None,
            training_steps=None,
            gradient_updates=0,
            training_seed=None,
        )

    def reset(self, seed: int) -> None:
        if self._scripted is not None:
            self._scripted.reset(seed)

    def decide(self, obs: np.ndarray, mask: np.ndarray) -> tuple[int, list[float] | None]:
        if self.agent is not None:
            q = self.agent.q_values(obs)
            return int(self.agent.greedy_action(obs, mask)), [float(x) for x in q]
        return int(self._scripted.act(obs, mask)), None


def run_lab_episode(
    scenario: ScenarioConfig,
    policy_kind: PolicyKind,
    episode_seed: int,
    *,
    checkpoint: Path = DEFAULT_CHECKPOINT,
    expected_sha256: str | None = DEFAULT_CHECKPOINT_SHA256,
    max_steps: int | None = None,
) -> LabEpisode:
    """Simulate one episode. Deterministic in (scenario, policy_kind, episode_seed).

    ``expected_sha256`` pins the checkpoint bytes; pass ``None`` only for a checkpoint whose
    sidecar manifest carries the digest (a locally trained run).
    """
    if not 0 <= episode_seed <= MAX_EPISODE_SEED:
        raise ValueError(f"episode_seed must be in [0, {MAX_EPISODE_SEED}]")
    if max_steps is not None and max_steps < 1:
        raise ValueError("max_steps must be >= 1")
    policy = _Policy(policy_kind, checkpoint, expected_sha256)
    env = DefenseSimEnv(scenario)
    obs, info = env.reset(seed=episode_seed)
    policy.reset(episode_seed)
    steps: list[LabEpisodeStep] = []
    total, done, terminated = 0.0, False, False
    counts: dict[str, int] = {}
    while not done and (max_steps is None or len(steps) < max_steps):
        mask = info["action_mask"]
        action, q = policy.decide(obs, mask)
        if not mask[action]:
            raise RuntimeError(f"policy {policy_kind} chose masked action {action}")
        next_obs, reward, terminated, truncated, info = env.step(action)
        label = action_label(action)
        counts[label] = counts.get(label, 0) + 1
        steps.append(
            LabEpisodeStep(
                t=len(steps),
                observation=[float(x) for x in obs],
                action_mask=[bool(x) for x in mask],
                q_values=q,
                action=action,
                action_label=label,
                reward=float(reward),
                reward_components={
                    k: float(info["events"]["reward_components"][k]) for k in REWARD_COMPONENTS
                },
                terminated=terminated,
                truncated=truncated,
                ground_truth_stages=[STAGE_NAMES[s] for s in info["metrics"]["stages"]],
            )
        )
        total += reward
        obs, done = next_obs, terminated or truncated
    m = info["metrics"]
    return LabEpisode(
        episode_seed=episode_seed,
        scenario=LabEpisodeScenario(
            name=scenario.name,
            split=scenario.split,  # type: ignore[arg-type]
            config_hash=scenario.config_hash(),
            horizon=scenario.horizon,
            nodes=[
                LabEpisodeNode(
                    name=n.name,
                    criticality=n.criticality,
                    exposed=n.exposed,
                    finding_severity=n.finding_severity,
                )
                for n in scenario.nodes
            ],
            edges=[tuple(e) for e in scenario.edges],
        ),
        policy=policy.info,
        feature_names=list(FEATURE_NAMES),
        action_labels=list(ACTION_LABELS),
        reward_component_names=list(REWARD_COMPONENTS),
        steps=steps,
        final_observation=[float(x) for x in obs],
        summary=LabEpisodeSummary(
            total_return=float(total),
            steps=len(steps),
            terminated=bool(terminated),
            ever_impact=bool(m["ever_impact"]),
            impact_nodes=list(m["impact_nodes"]),
            first_foothold_t=m["first_foothold_t"],
            containment_t=m["containment_t"],
            action_counts=counts,
        ),
    )


def main() -> None:
    names = sorted(scenarios())
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--scenario", choices=names, required=True)
    ap.add_argument("--policy", choices=POLICY_KINDS, required=True)
    ap.add_argument("--seed", type=int, default=1000)
    ap.add_argument("--max-steps", type=int)
    ap.add_argument("--out", type=Path, help="write the full episode JSON here")
    args = ap.parse_args()
    episode = run_lab_episode(
        scenarios()[args.scenario], args.policy, args.seed, max_steps=args.max_steps
    )
    if args.out:
        args.out.write_text(episode.model_dump_json(indent=2))
    print(json.dumps({"policy": episode.policy.model_dump(), **episode.summary.model_dump()}))


if __name__ == "__main__":
    main()
