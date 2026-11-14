"""The pilot gate: frozen, unused scenarios and fail-closed checks. No gate scenario is run
here; plumbing is exercised on a training scenario."""

import yaml

from rl_defense.live import evaluate as ev
from rl_defense.live import pilot_gate as pg
from rl_defense.live.scenarios import CONFIG_DIR, load_scenarios


def _split(name: str) -> str:
    return "train" if name.startswith("train") else "val" if name.startswith("val") else "holdout"


def test_gate_scenarios_are_disjoint_from_every_other_split():
    gate = load_scenarios("holdout", subdir=pg.SCENARIO_DIR)
    assert len(gate) == 4 and all(s.episodes == 30 for s in gate)
    names, seeds = set(), set()
    for d in sorted(p for p in CONFIG_DIR.iterdir() if p.is_dir() and p.name != pg.SCENARIO_DIR):
        for s in load_scenarios(_split(d.name), subdir=d.name):
            names.add(s.name)
            seeds.update(s.seeds())
    for s in gate:
        assert s.name not in names and not seeds & set(s.seeds())
    assert len({x for s in gate for x in s.seeds()}) == 120


def test_pinned_inputs_match_their_hashes():
    pg._pinned(pg.CANDIDATE, pg.CANDIDATE_SHA256)
    pg._pinned(pg.RULES_TUNING, pg.RULES_TUNING_SHA256)
    pg._pinned(pg.CRITERIA, pg.CRITERIA_SHA256)


def _rows(reward: float, **over: int) -> list[ev.EpisodeMetrics]:
    base = dict(
        steps=10, attack_requests=10, compromised=1, benign_requests=20, benign_blocked=1,
        benign_requests_no_attack=5, benign_blocked_no_attack=0, steps_no_attack=5,
        disruptive_steps_no_attack=0, nonnoop_actions=1,
    )  # fmt: skip
    base.update(over)
    return [ev.EpisodeMetrics("s", i, reward - 0.01 * i, **base) for i in range(10)]


def _access(ok: int, total: int = 10) -> list[dict]:
    return [
        {"scenario": "s", "seed": i, "own_requests": 5, "own_succeeded": 5,
         "delegated_requests": total, "delegated_succeeded": ok}
        for i in range(10)
    ]  # fmt: skip


def test_gate_needs_every_check_including_delegated_access():
    criteria = ev.PromotionCriteria(**yaml.safe_load(pg.CRITERIA.read_text()))
    rules, good = _rows(-5.0, compromised=5), _rows(-1.0)
    assert pg.gate(good, rules, _access(9), criteria)["passed"]
    low = pg.gate(good, rules, _access(8), criteria)
    assert not low["passed"]
    assert [c["name"] for c in low["checks"] if not c["passed"]] == ["delegated_success_floor"]
    undefined = pg.gate(good, rules, _access(0, 0), criteria)
    assert not undefined["passed"]
    # a higher return does not excuse more compromise than the rules
    worse = pg.gate(_rows(-1.0, compromised=8), rules, _access(10), criteria)
    assert "compromise_rate_not_worse" in [c["name"] for c in worse["checks"] if not c["passed"]]


def test_runner_measures_delegated_access_on_a_training_scenario():
    sc = load_scenarios("train", subdir="train_v3")[:1]
    rows, access, decisions = pg.run_policy(ev.noop_policy, sc, episodes=1)
    reference = ev.run_policy(
        ev.noop_policy, sc, pg.live_app, episodes=1, action_space=pg.SPACE,
        loop_overrides=ev.V4_LOOP_OVERRIDES,
    )  # fmt: skip
    assert rows == reference and decisions == []
    assert access[0]["delegated_requests"] > 0
    assert pg.access_summary(access)["delegated_success"] == 1.0  # nothing blocks under noop
