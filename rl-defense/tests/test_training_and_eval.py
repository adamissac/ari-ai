"""Short end-to-end runs: real training updates, checkpoint reload, protocol evaluation, inference."""

import json

import numpy as np
import pytest

from rl_defense.agents.ddqn import DDQNConfig
from rl_defense.api import checkpoint_ref, load_eval_summary, load_policy
from rl_defense.baselines import (
    NoopPolicy,
    RandomValidPolicy,
    ThresholdParams,
    ThresholdRulesPolicy,
)
from rl_defense.contracts import DefenseRecommendation, NodeSignals, PlatformFacts
from rl_defense.envs import DefenseSimEnv, default_config_paths, load_configs
from rl_defense.envs.defense_sim import NOOP_ACTION, OBS_DIM
from rl_defense.evaluate import evaluate, holm
from rl_defense.observations import from_platform_facts, mask_from_facts
from rl_defense.train import train

TRAIN = load_configs(default_config_paths("train"))
EVAL = load_configs(default_config_paths("eval"))
SMALL = DDQNConfig(
    learning_starts=200, buffer_size=5_000, eps_decay_steps=2_000, target_update_interval=200
)


@pytest.fixture(scope="module")
def trained_run(tmp_path_factory):
    run = tmp_path_factory.mktemp("run")
    manifests = [
        train(TRAIN, seed=s, steps=3_000, run_dir=run, ddqn_config=SMALL, log_every=1_000)
        for s in (0, 1)
    ]
    return run, manifests


def test_training_performs_real_gradient_updates(trained_run):
    _, manifests = trained_run
    for m in manifests:
        assert m["gradient_updates"] == 3_000 - SMALL.learning_starts
        assert m["param_abs_change"] > 0
        assert m["episodes"] > 0


def test_training_is_seed_deterministic(tmp_path):
    a = train(TRAIN, seed=7, steps=600, run_dir=tmp_path / "a", ddqn_config=SMALL)
    b = train(TRAIN, seed=7, steps=600, run_dir=tmp_path / "b", ddqn_config=SMALL)
    assert a["param_abs_change"] == b["param_abs_change"]


def test_training_refuses_eval_configs(tmp_path):
    with pytest.raises(ValueError, match="split=train"):
        train(EVAL, seed=0, steps=10, run_dir=tmp_path)


def test_evaluation_protocol_outputs(trained_run):
    run, _ = trained_run
    summary = evaluate(run, EVAL, TRAIN, episodes=range(1000, 1004), trajectories_per_policy=1)
    assert set(summary["policies"]) == {"ddqn", "random", "noop", "threshold_rules"}
    assert summary["training_seeds"] == [0, 1]
    assert summary["eval_seed_range"] == [1000, 1003]
    assert set(summary["eval_configs"]) == {c.name for c in EVAL}
    assert summary["caveat"].startswith("Results are from a simulated environment")
    pooled = summary["policies"]["ddqn"]["pooled"]
    assert len(pooled["return"]["per_seed"]) == 2
    assert (
        pooled["invalid_actions"]["mean"] == 0
    )  # masking means the agent never picks invalid actions
    assert set(summary["comparisons"]) == {
        "ddqn_vs_random",
        "ddqn_vs_noop",
        "ddqn_vs_threshold_rules",
    }
    assert (run / "eval_table.md").read_text().count("| ddqn |") == 2
    raw = [json.loads(line) for line in (run / "eval_episodes.jsonl").read_text().splitlines()]
    assert len(raw) == 4 * 2 * len(EVAL) * 4  # policies × seeds × configs × episodes
    assert any((run / "trajectories").iterdir())
    assert load_eval_summary(run)["env_id"] == "DefenseSimEnv-v0"


def test_analysis_report_and_deterministic_failure_replays(trained_run):
    from rl_defense.analysis import analyze

    run, _ = trained_run
    if not (run / "eval_episodes.jsonl").exists():
        evaluate(run, EVAL, TRAIN, episodes=range(1000, 1004), trajectories_per_policy=1)
    text = analyze(run, n_failures=2)
    for section in (
        "Where each policy loses reward",
        "Which nodes fall",
        "Action mix",
        "Failure cases",
    ):
        assert section in text
    cases = sorted((run / "failure_cases").glob("ddqn_*.json"))
    assert len(cases) == 2  # replay_episode asserts the replayed return equals the recorded one


def test_holm_correction():
    assert holm({"a": 0.01, "b": 0.04, "c": 0.03}) == {"a": True, "b": False, "c": False}
    assert holm({"a": 0.001, "b": 0.02}) == {"a": True, "b": True}


def _facts(**over):
    rows = [
        ("gateway", 0.3, True, 0.3),
        ("api", 0.5, True, 0.5),
        ("auth", 0.7, False, 0.2),
        ("payments", 0.9, False, 0.6),
        ("db", 1.0, False, 0.1),
    ]
    nodes = tuple(
        NodeSignals(node=n, criticality=c, exposed=e, finding_severity=s, **over.get(n, {}))
        for n, c, e, s in rows
    )
    return PlatformFacts(project_id="prj_test", nodes=nodes)


def test_observation_mapping_matches_env_layout():
    env = DefenseSimEnv(TRAIN[0])
    obs, info = env.reset(seed=0)
    facts = PlatformFacts(
        project_id=None,
        nodes=tuple(
            NodeSignals(
                node=n.name,
                criticality=n.criticality,
                exposed=n.exposed,
                finding_severity=n.finding_severity,
                alert_rate=float(env._obs_state.alert_history.mean(axis=0)[i]),
                anomaly_score=float(env._obs_state.anomaly[i]),
            )
            for i, n in enumerate(TRAIN[0].nodes)
        ),
    )
    np.testing.assert_allclose(from_platform_facts(facts), obs, atol=1e-6)
    np.testing.assert_array_equal(mask_from_facts(facts), info["action_mask"])


def test_inference_recommendation_is_typed_masked_and_labeled(trained_run):
    run, _ = trained_run
    ckpt = run / "ddqn_seed0.pt"
    runner = load_policy(ckpt)
    rec = runner.recommend(_facts(api={"isolated": True, "anomaly_score": 0.9, "alert_rate": 6.0}))
    assert isinstance(rec, DefenseRecommendation)
    assert rec.simulation_derived is True and "simulation" in rec.caveat
    assert not (rec.action in ("isolate", "rate_limit") and rec.node == "api"), (
        "masked action recommended"
    )
    assert rec.q_margin >= 0
    assert rec.policy_version.startswith("DefenseSimEnv-v0@")
    assert DefenseRecommendation.model_validate_json(rec.model_dump_json()) == rec
    ref = checkpoint_ref(ckpt)
    assert ref.checkpoint_sha256 == rec.checkpoint_sha256


def test_inference_is_deterministic(trained_run):
    run, _ = trained_run
    runner = load_policy(run / "ddqn_seed0.pt")
    a, b = runner.recommend(_facts()), runner.recommend(_facts())
    assert (a.action, a.node, a.q_margin) == (b.action, b.node, b.q_margin)


def test_random_baseline_seeds_are_distinct_but_reproducible():
    def actions(policy_seed, episode_seed):
        env = DefenseSimEnv(EVAL[0])
        pol = RandomValidPolicy(policy_seed)
        obs, info = env.reset(seed=episode_seed)
        pol.reset(episode_seed)
        out = []
        for _ in range(30):
            a = pol.act(obs, info["action_mask"])
            out.append(a)
            obs, _, term, trunc, info = env.step(a)
            if term or trunc:
                break
        return out

    assert actions(0, 1000) == actions(0, 1000)
    assert actions(0, 1000) != actions(1, 1000)


def test_baselines_only_choose_valid_actions():
    env = DefenseSimEnv(EVAL[0])
    for pol in (
        NoopPolicy(),
        RandomValidPolicy(0),
        ThresholdRulesPolicy(ThresholdParams(0.2, 0.3, 0.1)),
    ):
        obs, info = env.reset(seed=1)
        pol.reset(1)
        for _ in range(100):
            a = pol.act(obs, info["action_mask"])
            assert info["action_mask"][a]
            obs, _, term, trunc, info = env.step(a)
            if term or trunc:
                break
    assert NoopPolicy().act(np.zeros(OBS_DIM), np.ones(22, dtype=bool)) == NOOP_ACTION


def test_defense_lab_bundle_exports_valid_typed_replays(trained_run):
    from rl_defense.lab_export import DefenseLabBundle, export

    run, _ = trained_run
    if not (run / "eval_summary.json").exists():
        evaluate(run, EVAL, TRAIN, episodes=range(1000, 1004), trajectories_per_policy=1)
    bundle = export(run)
    again = DefenseLabBundle.model_validate_json(bundle.model_dump_json())
    assert again.simulation_only is True and "simulated" in again.caveat
    assert {e.policy for e in again.episodes} == {"ddqn", "threshold_rules", "noop"}
    step = again.episodes[0].steps[0]
    assert len(step.nodes) == 5
    assert abs(sum(step.reward_components.values()) - step.reward) < 1e-2
