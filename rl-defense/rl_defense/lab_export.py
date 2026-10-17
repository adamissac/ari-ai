"""Export a typed, UI-ready Defense Lab bundle from an evaluated run.

    python -m rl_defense.lab_export --run-dir runs/<run_id> --out <file>.json [--schema <file>]

Everything in the bundle is real evaluation output or a deterministic replay of
it. Hidden adversary stages are included only as clearly labeled ground truth for
replay visualization; policies never observe them.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from rl_defense import ENV_ID
from rl_defense.baselines import NoopPolicy, ThresholdParams, ThresholdRulesPolicy
from rl_defense.envs import DefenseSimEnv, default_config_paths, load_configs
from rl_defense.envs.config import NODE_NAMES, ScenarioConfig
from rl_defense.envs.defense_sim import NODE_FEATURES
from rl_defense.evaluate import CAVEAT, DDQNPolicy, run_episode

LAB_SCHEMA_VERSION = "0.1.0"
STAGE_NAMES = ("none", "foothold", "escalated", "impact")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LabNode(_Strict):
    name: str
    criticality: float
    exposed: bool
    finding_severity: float


class LabScenario(_Strict):
    name: str
    config_hash: str
    split: Literal["eval"]
    horizon: int
    nodes: list[LabNode]
    edges: list[tuple[str, str]]


class MetricCI(_Strict):
    mean: float | None
    ci95: tuple[float | None, float | None]


class LabPolicyMetrics(_Strict):
    policy: str
    pooled: dict[str, MetricCI]
    per_scenario: dict[str, dict[str, MetricCI]]


class LabNodeState(_Strict):
    node: str
    alert_rate: float
    anomaly_score: float
    monitoring_level: float
    rate_limited: bool
    isolated: bool
    reassessment_pending: bool
    hidden_stage_ground_truth: Literal["none", "foothold", "escalated", "impact"] = Field(
        description="Replay visualization only. The policy never observes this."
    )


class LabStep(_Strict):
    t: int
    action: str
    reward: float
    reward_components: dict[str, float]
    nodes: list[LabNodeState]


class LabEpisode(_Strict):
    policy: str
    scenario: str
    episode_seed: int
    training_seed: int | None
    total_return: float
    compromised: bool
    impact_nodes: list[str]
    steps: list[LabStep]


class DefenseLabBundle(_Strict):
    schema_version: str = LAB_SCHEMA_VERSION
    env_id: str = ENV_ID
    simulation_only: Literal[True] = True
    caveat: str = CAVEAT
    source_run: str
    git_sha: str
    checkpoint_sha256: dict[str, str]
    training_seeds: list[int]
    episodes_per_config_per_seed: int
    scenarios: list[LabScenario]
    metrics: list[LabPolicyMetrics]
    episodes: list[LabEpisode]


def _ci(m: dict) -> MetricCI:
    return MetricCI(mean=m["mean"], ci95=tuple(m["ci95"]))  # type: ignore[arg-type]


def _scenario(c: ScenarioConfig) -> LabScenario:
    return LabScenario(
        name=c.name,
        config_hash=c.config_hash(),
        split="eval",
        horizon=c.horizon,
        nodes=[
            LabNode(
                name=n.name,
                criticality=n.criticality,
                exposed=n.exposed,
                finding_severity=n.finding_severity,
            )
            for n in c.nodes
        ],
        edges=[tuple(e) for e in c.edges],  # type: ignore[misc]
    )


def _episode(
    policy_name: str, policy, cfg: ScenarioConfig, seed: int, tseed: int | None
) -> LabEpisode:  # noqa: ANN001
    row, traj = run_episode(DefenseSimEnv(cfg), policy, seed, record=True)
    nf = len(NODE_FEATURES)
    idx = {f: NODE_FEATURES.index(f) for f in NODE_FEATURES}
    steps = []
    for s in traj:
        obs = s["observation"]
        steps.append(
            LabStep(
                t=s["t"],
                action=s["action"],
                reward=s["reward"],
                reward_components=s["reward_components"],
                nodes=[
                    LabNodeState(
                        node=name,
                        alert_rate=round(obs[i * nf + idx["alert_rate"]], 3),
                        anomaly_score=round(obs[i * nf + idx["anomaly_score"]], 3),
                        monitoring_level=round(obs[i * nf + idx["monitoring_level"]], 3),
                        rate_limited=obs[i * nf + idx["rate_limited"]] > 0.5,
                        isolated=obs[i * nf + idx["isolated"]] > 0.5,
                        reassessment_pending=obs[i * nf + idx["reassessment_pending"]] > 0.5,
                        hidden_stage_ground_truth=STAGE_NAMES[
                            s["hidden_stages_for_replay_only"][i]
                        ],
                    )
                    for i, name in enumerate(NODE_NAMES)
                ],
            )
        )
    return LabEpisode(
        policy=policy_name,
        scenario=cfg.name,
        episode_seed=seed,
        training_seed=tseed,
        total_return=row["return"],
        compromised=bool(row["compromise_rate"]),
        impact_nodes=row["impact_nodes"],
        steps=steps,
    )


def export(run_dir: Path, episode_seeds: tuple[int, ...] = (1000,)) -> DefenseLabBundle:
    summary = json.loads((run_dir / "eval_summary.json").read_text())
    configs = load_configs(default_config_paths("eval"))
    tseed = summary["training_seeds"][0]
    ddqn = DDQNPolicy(run_dir / f"ddqn_seed{tseed}.pt")
    thr = ThresholdRulesPolicy(ThresholdParams(**summary["threshold_rules"]["params"]))
    episodes = []
    for cfg in configs:
        for seed in episode_seeds:
            episodes.append(_episode("ddqn", ddqn, cfg, seed, tseed))
            episodes.append(_episode("threshold_rules", thr, cfg, seed, None))
            episodes.append(_episode("noop", NoopPolicy(), cfg, seed, None))
    metrics = [
        LabPolicyMetrics(
            policy=p,
            pooled={k: _ci(v) for k, v in entry["pooled"].items()},
            per_scenario={
                c: {k: _ci(v) for k, v in ms.items()} for c, ms in entry["per_config"].items()
            },
        )
        for p, entry in summary["policies"].items()
    ]
    return DefenseLabBundle(
        source_run=run_dir.name,
        git_sha=summary["git_sha"],
        checkpoint_sha256=summary["checkpoints"],
        training_seeds=summary["training_seeds"],
        episodes_per_config_per_seed=summary["episodes_per_config_per_seed"],
        scenarios=[_scenario(c) for c in configs],
        metrics=metrics,
        episodes=episodes,
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--schema", type=Path, help="also write the bundle's JSON Schema here")
    args = ap.parse_args()
    bundle = export(args.run_dir)
    args.out.write_text(bundle.model_dump_json() + "\n")
    if args.schema:
        args.schema.write_text(json.dumps(DefenseLabBundle.model_json_schema(), indent=2) + "\n")
    print(
        f"wrote {args.out} ({args.out.stat().st_size // 1024} KiB, {len(bundle.episodes)} episodes)"
    )


if __name__ == "__main__":
    main()
