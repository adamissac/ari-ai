"""Split hygiene and five-seed aggregation. Never execute holdout_v9 in CI."""

from __future__ import annotations

import copy
from dataclasses import asdict

import pytest

from rl_defense.live import study
from rl_defense.live.online import OnlineConfig
from rl_defense.live.scenarios import CONFIG_DIR, load_scenarios


def test_validation_keeps_v4_and_adds_quiet_regimes():
    old = {s.name: s.config_hash() for s in load_scenarios("val", subdir="val_v4")}
    new = {s.name: s for s in load_scenarios("val", subdir="val_v9")}
    assert len(new) == len(old) + 2
    assert all(new[n].config_hash() == h for n, h in old.items())
    for name in set(new) - set(old):
        sc = new[name]
        assert sc.attack_per_step == 2 and sc.p_start == 0.05
        assert sc.p_stop >= 0.35 and sc.benign_per_step == 9
        sc.driver()


def test_v9_new_scenarios_and_seeds_are_disjoint():
    others = []
    for directory in CONFIG_DIR.iterdir():
        if not directory.is_dir() or directory.name in {"val_v9", "holdout_v9"}:
            continue
        split = directory.name.split("_")[0]
        if split in {"train", "val", "holdout"}:
            others += load_scenarios(split, subdir=directory.name)
    existing_names = {s.name for s in others}
    existing_seeds = {seed for s in others for seed in s.seeds()}
    additions = [s for s in load_scenarios("val", subdir="val_v9") if s.name.startswith("val9_")]
    holdout = load_scenarios("holdout", subdir="holdout_v9")
    assert len(holdout) == 3 and all(s.episodes == 100 for s in holdout)
    new_names, new_seeds = set(), set()
    for sc in additions + holdout:
        assert sc.name not in existing_names | new_names
        assert set(sc.seeds()).isdisjoint(existing_seeds | new_seeds)
        new_names.add(sc.name)
        new_seeds.update(sc.seeds())
        sc.driver()  # validates config; does not execute any requests/episode


def _reports():
    return [
        {
            "git_sha": "source",
            "rules_episodes": 2,
            "expert": {"name": "rules"},
            "rules_params": {"threshold": 0.1},
            "online": asdict(OnlineConfig(seed=seed)),
            "splits": {"holdout": {"fresh": "hash"}},
            "criteria": {},
            "loop_overrides": {},
            "action_space": "live_v3",
            "deployed": {"checkpoint_sha256": "incumbent"},
            "holdout_episodes_per_scenario": 100,
            "caveat": "lab only",
            "policies": {
                "candidate": {m: float(seed) for m in study.METRICS},
                "deployed": {m: 0.0 for m in study.METRICS},
            },
            "by_scenario": {
                n: {"fresh": {m: float(seed) for m in study.METRICS}}
                for n in ("candidate", "deployed")
            },
            "decision": "reject",
            "checks": [],
        }
        for seed in range(5)
    ]


def test_aggregate_uses_all_training_seeds_and_not_best_seed():
    reports = _reports()
    for r in reports:
        r["by_scenario"] = {name: {"fresh": values} for name, values in r["policies"].items()}
    result = study.aggregate(list(reversed(reports)))
    assert result["by_scenario"]["candidate"]["fresh"]["reward"]["mean"] == 2.0
    r = result["policies"]["candidate"]["reward"]
    assert r["mean"] == 2.0 and r["by_training_seed"] == [0, 1, 2, 3, 4]
    assert r["ci95"][0] < 2 < r["ci95"][1]
    assert result["promotion_performed"] is False
    assert len(result["per_seed_gate"]) == 5
    for comparison in result["candidate_minus_incumbent"].values():
        assert comparison["holm_p"] >= comparison["paired_t_p_two_sided"]


@pytest.mark.parametrize(
    "field", ["splits", "criteria", "loop_overrides", "action_space", "deployed"]
)
def test_aggregate_refuses_incomparable_runs(field):
    reports = _reports()
    reports[2][field] = "mismatch"
    with pytest.raises(ValueError, match=field):
        study.aggregate(reports)


def test_aggregate_refuses_missing_duplicated_seeds_and_undefined_metrics():
    reports = _reports()
    with pytest.raises(ValueError, match="exactly training seeds"):
        study.aggregate(reports[:-1])
    bad = copy.deepcopy(reports)
    bad[-1]["online"]["seed"] = 3
    with pytest.raises(ValueError, match="exactly training seeds"):
        study.aggregate(bad)
    reports[0]["policies"]["candidate"]["false_disruption"] = None
    with pytest.raises(ValueError, match="undefined"):
        study.aggregate(reports)


@pytest.mark.parametrize(
    "field", ["env_steps", "pretrain_updates", "demo_fraction", "val_episodes"]
)
def test_aggregate_refuses_different_training_and_selection_budgets(field):
    reports = _reports()
    reports[1]["online"][field] += 1
    with pytest.raises(ValueError, match=f"online setting {field}"):
        study.aggregate(reports)


def test_aggregate_refuses_missing_settings_changed_references_and_source():
    reports = _reports()
    del reports[0]["online"]["env_steps"]
    with pytest.raises(ValueError, match="missing online setting"):
        study.aggregate(reports)
    reports = _reports()
    for report in reports:
        report["references"] = [
            {"name": "v8", "checkpoint_sha256": "original", "env_id": "live_v3"}
        ]
    reports[1]["references"][0]["checkpoint_sha256"] = "swapped"
    with pytest.raises(ValueError, match="reference checkpoints"):
        study.aggregate(reports)
    reports = _reports()
    reports[1]["git_sha"] = "different"
    with pytest.raises(ValueError, match="source commit"):
        study.aggregate(reports)


@pytest.mark.parametrize("value", [None, "", "   "])
def test_aggregate_requires_source(value):
    reports = _reports()
    for report in reports:
        report["git_sha"] = value
    with pytest.raises(ValueError, match="source commit"):
        study.aggregate(reports)


@pytest.mark.parametrize("key", ["rules_episodes", "expert", "rules_params"])
def test_aggregate_rejects_different_teacher_selection(key):
    reports = _reports()
    reports[1][key] = 3 if key == "rules_episodes" else {"changed": True}
    with pytest.raises(ValueError, match="teacher-selection"):
        study.aggregate(reports)


def test_missing_teacher_budget_needs_explicit_historical_command_evidence():
    reports = _reports()
    for report in reports:
        del report["rules_episodes"]
    with pytest.raises(ValueError, match="rules_episodes"):
        study.aggregate(reports)
    assert study.aggregate(reports, legacy_rules_episodes=dict.fromkeys(range(5), 2))


@pytest.mark.parametrize("seed", [0, 2])
def test_aggregate_rejects_missing_scenario_in_any_report(seed):
    reports = _reports()
    del reports[seed]["by_scenario"]["candidate"]["fresh"]
    with pytest.raises(ValueError, match="holdout scenario"):
        study.aggregate(reports)
