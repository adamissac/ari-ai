"""Defense Lab simulation route: a real simulated episode on request, or an explicit 503.

The route never touches a project or a control. The positive tests run the real
``rl_defense`` engine and the committed, hash-pinned checkpoint, and skip when the engine
is not installed in this environment. The failure tests always run.
"""

from __future__ import annotations

import importlib.util
from concurrent.futures import ThreadPoolExecutor

import pytest

from backend.api import lab

BASE = "/api/v1/lab/simulation"
BODY = {"scenario": "eval_aggressive_noisy", "policy": "ddqn_trained", "episode_seed": 1003}
needs_engine = pytest.mark.skipif(
    importlib.util.find_spec("rl_defense") is None or importlib.util.find_spec("torch") is None,
    reason="rl_defense/torch not installed in this environment",
)


@pytest.fixture(autouse=True)
def fresh_cache():
    lab._episode.cache_clear()
    yield
    lab._episode.cache_clear()


def test_requires_sign_in_and_csrf(client_factory):
    anonymous = client_factory()
    assert anonymous.get(BASE).status_code == 401
    assert anonymous.post(f"{BASE}/episodes", json=BODY).status_code == 401
    alice = client_factory("alice")
    del alice.headers["X-CSRF-Token"]
    assert alice.post(f"{BASE}/episodes", json=BODY).status_code == 403


def test_bad_requests_are_rejected(client_factory):
    alice = client_factory("alice")
    for body in (
        {**BODY, "policy": "ppo"},
        {**BODY, "episode_seed": -1},
        {**BODY, "episode_seed": 2**31},
        {**BODY, "scenario": "../../etc/passwd"},
        {**BODY, "extra": 1},
    ):
        assert alice.post(f"{BASE}/episodes", json=body).status_code == 422, body


def test_missing_engine_is_an_explicit_503_not_a_fake_episode(client_factory, monkeypatch):
    def gone():
        raise lab.LabUnavailable("the simulation engine is not installed in this API process")

    monkeypatch.setattr(lab, "_engine", gone)
    alice = client_factory("alice")
    status = alice.get(BASE).json()
    assert status["available"] is False and "not installed" in status["unavailable_reason"]
    assert status["scenarios"] == [] and status["checkpoint"] is None
    r = alice.post(f"{BASE}/episodes", json=BODY)
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "SUBSYSTEM_UNAVAILABLE"
    assert "episode" not in r.json()


@needs_engine
def test_swapped_checkpoint_is_refused(client_factory, monkeypatch, tmp_path):
    swapped = tmp_path / "ddqn_seed0.pt"
    swapped.write_bytes(lab.LAB_CHECKPOINT.read_bytes() + b"x")
    monkeypatch.setattr(lab, "LAB_CHECKPOINT", swapped)
    alice = client_factory("alice")
    status = alice.get(BASE).json()
    assert status["available"] is False and "pinned sha256" in status["unavailable_reason"]
    assert alice.post(f"{BASE}/episodes", json=BODY).status_code == 503
    # the baselines do not load the checkpoint, but the lab still refuses to run degraded
    assert alice.post(f"{BASE}/episodes", json={**BODY, "policy": "noop"}).status_code == 503


@needs_engine
def test_status_lists_real_scenarios_and_the_pinned_checkpoint(client_factory):
    status = client_factory("alice").get(BASE).json()
    assert status["available"] is True and status["unavailable_reason"] is None
    assert {s["name"] for s in status["scenarios"]} >= {"eval_aggressive_noisy", "train_balanced"}
    assert status["scenarios"][0]["split"] == "eval"
    assert status["policies"] == [
        "ddqn_trained",
        "ddqn_untrained",
        "random",
        "noop",
        "threshold_rules",
    ]
    assert status["checkpoint"]["sha256"] == lab.LAB_CHECKPOINT_SHA256
    assert "simulat" in status["label"].lower()


@needs_engine
def test_episode_is_the_engine_output_and_is_labelled_a_simulation(client_factory):
    from rl_defense.lab_episode import LabEpisode, run_lab_episode, scenarios

    r = client_factory("alice").post(f"{BASE}/episodes", json=BODY)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "no action is executed" in body["label"]
    episode = LabEpisode.model_validate(body["episode"])
    direct = run_lab_episode(scenarios()[BODY["scenario"]], "ddqn_trained", BODY["episode_seed"])
    assert episode == direct
    assert episode.kind == "simulation"
    assert episode.policy.source == "learned_checkpoint"
    assert episode.policy.checkpoint_sha256 == lab.LAB_CHECKPOINT_SHA256
    assert episode.policy.gradient_updates > 0
    step = episode.steps[0]
    assert len(step.q_values) == len(step.action_mask) == 22 and step.action_mask[step.action]
    assert episode.summary.total_return == pytest.approx(sum(s.reward for s in episode.steps))


@needs_engine
def test_policy_kinds_differ_and_the_untrained_network_is_labelled(client_factory):
    alice = client_factory("alice")

    def run(policy):
        r = alice.post(f"{BASE}/episodes", json={**BODY, "policy": policy})
        assert r.status_code == 200, r.text
        return r.json()["episode"]

    trained, untrained, rules = run("ddqn_trained"), run("ddqn_untrained"), run("threshold_rules")
    assert untrained["policy"]["source"] == "untrained_network"
    assert untrained["policy"]["gradient_updates"] == 0
    assert rules["policy"]["source"] == "scripted_baseline"
    assert rules["steps"][0]["q_values"] is None
    # same episode seed: every policy starts from the same observation, then diverges
    assert trained["steps"][0]["observation"] == untrained["steps"][0]["observation"]
    returns = {
        e["policy"]["kind"]: e["summary"]["total_return"] for e in (trained, untrained, rules)
    }
    assert len(set(returns.values())) == 3


@needs_engine
def test_unknown_scenario_is_a_validation_error(client_factory):
    r = client_factory("alice").post(f"{BASE}/episodes", json={**BODY, "scenario": "nope"})
    assert r.status_code == 422 and "unknown scenario" in r.text


@needs_engine
def test_concurrent_users_and_repeats_get_identical_independent_episodes(client_factory):
    alice, bob = client_factory("alice"), client_factory("bob")
    jobs = [
        (alice, {**BODY, "policy": "threshold_rules"}),
        (bob, {**BODY, "policy": "threshold_rules", "episode_seed": 1004}),
        (alice, {**BODY, "policy": "threshold_rules"}),
        (bob, {**BODY, "policy": "random"}),
    ]
    with ThreadPoolExecutor(max_workers=4) as pool:
        out = list(pool.map(lambda j: j[0].post(f"{BASE}/episodes", json=j[1]).json(), jobs))
    assert out[0] == out[2]
    assert out[0]["episode"]["episode_seed"] == 1003 and out[1]["episode"]["episode_seed"] == 1004
    assert out[0]["episode"]["steps"][5] != out[1]["episode"]["steps"][5]
    assert out[3]["episode"]["policy"]["kind"] == "random"


def test_rate_limit(client_factory, monkeypatch):
    monkeypatch.setattr(lab, "EPISODES_PER_HOUR", 2)
    monkeypatch.setattr(lab, "_episode", lambda *a: {"stub": True})
    alice = client_factory("alice")
    assert alice.post(f"{BASE}/episodes", json=BODY).status_code == 200
    assert alice.post(f"{BASE}/episodes", json=BODY).status_code == 200
    assert alice.post(f"{BASE}/episodes", json=BODY).status_code == 429


def test_lab_routes_cannot_reach_a_project_or_a_control():
    """The lab router exposes exactly the status read and the simulate call."""
    routes = sorted((sorted(r.methods), r.path) for r in lab.router.routes)
    assert routes == [(["GET"], "/lab/simulation"), (["POST"], "/lab/simulation/episodes")]
