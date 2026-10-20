"""Split hygiene and five-seed aggregation. Never execute holdout_v9 in CI."""

from __future__ import annotations

import copy

import pytest

from rl_defense.live import study
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
            "online": {"seed": seed},
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
            "decision": "reject",
            "checks": [],
        }
        for seed in range(5)
    ]


def test_aggregate_uses_all_training_seeds_and_not_best_seed():
    reports = _reports()
    for r in reports:
        r["by_scenario"] = {name: {"scenario1": values} for name, values in r["policies"].items()}
    result = study.aggregate(list(reversed(reports)))
    assert result["by_scenario"]["candidate"]["scenario1"]["reward"]["mean"] == 2.0
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
