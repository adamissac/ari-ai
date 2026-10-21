"""Action-imbalance regression and fresh split hygiene; no v10 held-out execution."""

from pathlib import Path

import numpy as np
import pytest

from rl_defense.agents.ddqn import ReplayBuffer
from rl_defense.live import study
from rl_defense.live.scenarios import CONFIG_DIR, load_scenarios


def replay(seed=7):
    buf = ReplayBuffer(100, 1, 25, seed)
    # Mirrors a quiet-heavy teacher with two rare principal action classes.
    for i in range(100):
        action = 0 if i < 97 else (22 if i < 99 else 23)
        buf.add([i], action, i, [i + 1], False, np.ones(25, dtype=bool))
    return buf


def test_action_balancing_exposes_rare_block_and_extension_examples():
    uniform = replay().sample(6000)
    balanced = replay().sample(6000, balance_actions=True)
    assert (uniform.actions == 0).float().mean() > 0.94
    for action in (0, 22, 23):
        assert 0.30 < (balanced.actions == action).float().mean() < 0.37
    # Every row retains its genuine teacher action/reward/observation association.
    ids = balanced.obs[:, 0].numpy().astype(int)
    expected = np.where(ids < 97, 0, np.where(ids < 99, 22, 23))
    np.testing.assert_array_equal(balanced.actions.numpy(), expected)
    np.testing.assert_array_equal(balanced.rewards.numpy(), ids)


def test_balanced_sampling_is_seeded_and_only_uses_current_ring_contents():
    a, b = replay(), replay()
    np.testing.assert_array_equal(
        a.sample(128, balance_actions=True).obs, b.sample(128, balance_actions=True).obs
    )
    for i in range(100):
        a.add([1000 + i], 24, 0, [0], False, np.ones(25, dtype=bool))
    batch = a.sample(128, balance_actions=True)
    assert set(batch.actions.tolist()) == {24}
    assert batch.obs.min() >= 1000
    with pytest.raises(ValueError, match="empty"):
        ReplayBuffer(2, 1, 25, 0).sample(1, balance_actions=True)


def test_default_uniform_sampling_preserves_previous_rng_sequence():
    expected = np.random.default_rng(7).integers(0, 100, size=32)
    np.testing.assert_array_equal(replay().sample(32).obs[:, 0].numpy(), expected)


def test_v10_splits_are_fresh_without_executing_them():
    existing_seeds, existing_names = set(), set()
    for directory in CONFIG_DIR.iterdir():
        split = directory.name.split("_")[0]
        if (
            directory.is_dir()
            and split in {"train", "val", "holdout"}
            and directory.name not in {"val_v10", "holdout_v10"}
        ):
            for scenario in load_scenarios(split, subdir=directory.name):
                existing_seeds.update(scenario.seeds())
                existing_names.add(scenario.name)
    for split in ("val", "holdout"):
        scenarios = load_scenarios(split, subdir=f"{split}_v10")
        assert len(scenarios) == 3
        for scenario in scenarios:
            assert scenario.name not in existing_names
            assert existing_seeds.isdisjoint(scenario.seeds())
            existing_seeds.update(scenario.seeds())
            existing_names.add(scenario.name)
            scenario.driver()
            if split == "holdout":
                assert scenario.episodes == 100


def test_study_refuses_mixed_sampling_arms():
    # Reuse complete synthetic report fixtures; no checkpoint or policy execution.
    import importlib.util

    path = Path(__file__).with_name("test_live_v9.py")
    spec = importlib.util.spec_from_file_location("v9_fixture", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    reports = module._reports()
    reports[2]["balance_demo_actions"] = True
    with pytest.raises(ValueError, match="demonstration sampling"):
        study.aggregate(reports)


def test_balanced_demo_option_executes_real_updates_and_retains_lineage(tmp_path):
    from rl_defense.checkpoint import load_checkpoint
    from rl_defense.live import evaluate as ev
    from rl_defense.live import online
    from rl_defense.live.adversary import live_app
    from rl_defense.live.scenarios import LiveScenario

    def scenario(split, seed):
        return LiveScenario(
            name=f"v10_smoke_{split}",
            split=split,
            horizon=5,
            schedule="always",
            attack_per_step=2,
            benign_per_step=2,
            seed_start=seed,
            episodes=1,
        )

    config = online.OnlineConfig(
        demo_episodes_per_scenario=1,
        pretrain_updates=4,
        env_steps=5,
        batch_size=4,
        eval_every=5,
        val_episodes=1,
        noop_margins=(0.0,),
    )
    manifest = online.train_online(
        [scenario("train", 100)],
        [scenario("val", 20000)],
        live_app,
        ev.always_block_principal_long,
        tmp_path,
        cfg=config,
        balance_demo_actions=True,
        log=lambda *args, **kwargs: None,
    )
    assert manifest["online"]["balance_demo_actions"] is True
    assert manifest["online"]["experiment"]["updates"] == 9
    agent, loaded = load_checkpoint(tmp_path / "candidate_online.pt")
    assert agent.updates == 4 + loaded["online"]["selected_env_step"]


def test_two_arm_summary_pairs_seeds_and_requires_every_gate():
    import copy
    import importlib.util

    root = Path(__file__).parents[1]

    def load(name, path):
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    fixture = load("v9_summary_fixture", Path(__file__).with_name("test_live_v9.py"))
    module = load("v10_summary_test", root / "results/live-retrain-v10/summarize.py")
    reports = {arm: fixture._reports() for arm in ("uniform", "balanced")}
    for arm, rows in reports.items():
        for row in rows:
            row["balance_demo_actions"] = arm == "balanced"
            row["references"] = [
                {"name": "v8", "checkpoint_sha256": "fixed", "env_id": "live_v3"},
                {
                    "name": "v9",
                    "checkpoint_sha256": f"matched{row['online']['seed']}",
                    "env_id": "live_v3",
                },
            ]
            if arm == "balanced":
                row["policies"]["candidate"]["reward"] += 2
                row["decision"] = "recommend_promote"
                row["checks"] = [{"passed": True}]
    result = module.summarize(reports)
    assert result["balanced_minus_uniform"]["reward"]["by_training_seed"] == [2] * 5
    assert result["primary_hypothesis_supported"] is True
    assert result["promotion_performed"] is False
    bad = copy.deepcopy(reports)
    bad["balanced"][4]["checks"][0]["passed"] = False
    assert module.summarize(bad)["primary_hypothesis_supported"] is False
    bad = copy.deepcopy(reports)
    bad["balanced"][0]["rules_episodes"] = 3
    with pytest.raises(ValueError, match="teacher-selection"):
        module.summarize(bad)
