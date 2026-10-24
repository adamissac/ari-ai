"""Unit instrumentation only; no approved scenario comparison or model training."""

from dataclasses import replace

import numpy as np
import pytest
from gymnasium.utils.env_checker import check_env

from rl_defense.research.resource.baselines import POLICIES, action
from rl_defense.research.resource.env import FEATURES, INDEX, OBS_DIM, ResourceEnv
from rl_defense.research.resource.service import Arrival, Config, Service
from rl_defense.research.resource.workload import FAMILIES


def job(tick=0, *, source=0, route=1, work=4, attack=False):
    return Arrival(tick, source, route, work, attack)


def test_fifo_capacity_and_work_conservation():
    service = Service(Config(workers=1, queue_capacity=1, window_ticks=4))
    result = service.advance((job(), job(), job()))
    assert (result.offered, result.accepted, result.capacity_denials) == (3, 2, 1)
    assert (result.work, result.completed, len(service.pending), result.queue_max) == (4, 1, 1, 1)
    assert service.jobs[0].finished == 4
    assert service.jobs[1].consumed == 0
    service.assert_accounting()


def test_partial_timeout_and_completion_at_exact_deadline():
    cfg = Config(workers=1, queue_capacity=2, window_ticks=4, deadline_ticks=2)
    service = Service(cfg)
    result = service.advance((job(work=4),))
    assert result.work == 2 and result.timeouts == 1
    assert service.jobs[0].remaining == 2 and not service.pending
    timely = Service(cfg)
    assert timely.advance((job(work=2),)).completed == 1
    assert timely.jobs[0].finished == 2


def test_application_overhead_uses_real_modeled_capacity():
    service = Service(Config(workers=2, window_ticks=2))
    result = service.advance((job(work=2), job(work=2)), overhead=1)
    assert result.work == 3 and result.overhead == 1
    assert result.completed == 1


def test_rate_limit_has_both_security_effect_and_legitimate_collateral():
    arrivals = (job(work=2), job(work=2), job(work=2), job(work=2, attack=True))
    cfg = Config(workers=2, window_ticks=8)
    normal, limited = Service(cfg), Service(cfg)
    normal.advance(arrivals)
    limited.advance(arrivals, limit_kind="route", target=1, quota=1)
    assert limited.metrics()["adversarial_work"] < normal.metrics()["adversarial_work"]
    assert limited.metrics()["legitimate_rate_denied"] == 2
    assert limited.metrics()["legitimate_completed"] < normal.metrics()["legitimate_completed"]


def test_queue_state_changes_later_window_without_another_action():
    cfg = Config(workers=1, queue_capacity=1, window_ticks=2)
    busy, quiet = Service(cfg), Service(cfg)
    busy.advance((job(work=8), job(work=8)))
    quiet.advance(())
    assert busy.advance((job(2, work=1),)).capacity_denials == 1
    assert quiet.advance((job(2, work=1),)).completed == 1


def test_delay_duration_cooldown_budget_and_history():
    cfg = Config(
        workers=1,
        queue_capacity=4,
        window_ticks=2,
        horizon=6,
        application_budget=2,
        route_quota=1,
        duration=2,
        delay=1,
        cooldown=1,
    )
    script = tuple(tuple(job(i * 2, work=4) for _ in range(3)) for i in range(6))
    env = ResourceEnv(cfg, script=script)
    env.reset(seed=0)
    assert env.action_masks().tolist() == [True, True, False]
    env.step(1)
    assert env.last.limit_denials == 0
    assert not env.action_masks()[1]
    env.step(0)
    assert env.last.limit_denials == 2
    env.step(0)
    assert env.last.limit_denials == 2
    assert not env.action_masks()[1]  # one cooldown window
    env.step(0)
    assert env.action_masks()[1]
    env.step(1)
    assert env.used == 2 and not env.action_masks()[1]
    _, _, terminated, truncated, info = env.step(0)
    assert not terminated and truncated and env.control is None
    assert any(row["event"] == "episode_stop" for row in info["control_ledger"])
    with pytest.raises(RuntimeError):
        env.step(0)
    env.reset(seed=0)
    assert env.used == 0 and not env.service.pending and not env.ledger


@pytest.mark.parametrize("invalid", [-1, 3, True, 0.0, "0"])
def test_invalid_actions_rejected_without_advancing_service(invalid):
    env = ResourceEnv()
    env.reset(seed=0)
    with pytest.raises(ValueError):
        env.step(invalid)
    assert env.index == 0 and env.service.now == 0 and env.used == 0
    assert env.attempts[-1]["accepted"] is False


def test_exhausted_budget_and_unknown_telemetry_fail_closed():
    for env in (ResourceEnv(Config(application_budget=0)), ResourceEnv(telemetry=False)):
        obs, _ = env.reset(seed=0)
        assert env.action_masks().tolist() == [True, False, False]
        env.step(0)
        assert env.action_masks().tolist() == [True, False, False]
        with pytest.raises(ValueError):
            env.step(1)
    obs, _ = ResourceEnv(telemetry=False).reset(seed=0)
    assert obs[len(FEATURES) + INDEX["arrivals"]] == 0


def test_hidden_labels_never_change_observations_or_source_targets():
    cfg = Config(horizon=3)
    jobs = tuple((job(i * 8, source=1, work=8), job(i * 8, source=2, work=1)) for i in range(3))
    labels = tuple(tuple(replace(j, adversarial=not j.adversarial) for j in row) for row in jobs)
    left, right = ResourceEnv(cfg, script=jobs), ResourceEnv(cfg, script=labels)
    np.testing.assert_array_equal(left.reset(seed=1)[0], right.reset(seed=1)[0])
    for a in (0, 2, 0):
        lo, _, _, _, li = left.step(a)
        ro, _, _, _, ri = right.step(a)
        np.testing.assert_array_equal(lo, ro)
        assert left._source_target() == right._source_target()
        assert li["action_seq"] > li["before_cutoff_seq"]
        assert all(e["available_seq"] < li["observation_cutoff_seq"] for e in left.service.events)
        assert li["window"] == ri["window"]


def test_future_arrivals_cannot_change_the_decision_prefix():
    cfg = Config(horizon=3)
    prefix = ((job(),), (job(8),))
    a = ResourceEnv(cfg, script=(*prefix, (job(16),)))
    b = ResourceEnv(cfg, script=(*prefix, tuple(job(16) for _ in range(20))))
    np.testing.assert_array_equal(a.reset(seed=1)[0], b.reset(seed=1)[0])
    for _ in range(2):
        np.testing.assert_array_equal(a.step(0)[0], b.step(0)[0])


@pytest.mark.parametrize("family", FAMILIES)
def test_seed_reproducibility_and_normalization(family):
    a, b = (
        ResourceEnv(Config(horizon=4), family=family),
        ResourceEnv(Config(horizon=4), family=family),
    )
    np.testing.assert_array_equal(a.reset(seed=5)[0], b.reset(seed=5)[0])
    for _ in range(4):
        x, y = a.step(0), b.step(0)
        np.testing.assert_array_equal(x[0], y[0])
        assert x[1:] == y[1:]
        assert len(x[0]) == OBS_DIM and a.observation_space.contains(x[0])


def test_all_baselines_use_only_the_observable_vector_and_mask():
    for policy in POLICIES:
        env = ResourceEnv(Config(horizon=6), family="mixed")
        obs, _ = env.reset(seed=0)
        for _ in range(6):
            selected = action(policy, obs)
            assert env.action_masks()[selected]
            obs, _, _, _, info = env.step(selected)
        assert env.used <= env.config.application_budget
        assert info["metrics_only"]["legitimate_offered"] == (
            info["metrics_only"]["legitimate_completed"]
            + info["metrics_only"]["legitimate_rate_denied"]
            + info["metrics_only"]["legitimate_capacity_denied"]
            + info["metrics_only"]["legitimate_timeouts"]
            + info["metrics_only"]["legitimate_pending"]
        )


def test_persistent_static_reference_has_explicit_different_capability():
    env = ResourceEnv(Config(horizon=3, application_budget=0), fixed_static=True)
    env.reset(seed=0)
    assert env.action_masks().tolist() == [True, False, False]
    windows = [env.step(0)[4] for _ in range(3)]
    assert sum(w["costs"]["applications"] for w in windows) == 1
    assert sum(w["costs"]["active_ticks"] for w in windows) == 24
    assert windows[0]["control_ledger"][0]["event"] == "static_reference"


def test_gymnasium_environment_contract_with_mask_aware_sampling(monkeypatch):
    env = ResourceEnv(Config(horizon=4))
    sample = env.action_space.sample
    # Gym's generic checker does not consume feasibility masks. Sample valid
    # choices while keeping the independent rejection behavior under test above.
    monkeypatch.setattr(
        env.action_space, "sample", lambda: sample(mask=env.action_masks().astype(np.int8))
    )
    check_env(env, skip_render_check=True)


def test_source_feasibility_includes_measured_backlog_work_without_new_arrivals():
    config = Config(workers=1, window_ticks=2, horizon=4)
    env = ResourceEnv(config, script=((job(source=1, work=16),), (), (), ()))
    env.reset(seed=0)
    env.step(0)
    env.step(0)
    assert env.last.offered == 0 and env.last.source_work[1] == 2
    assert env._source_target() == 1 and env.action_masks()[2]


def test_expiry_recovery_is_accounted_at_the_observation_boundary():
    service = Service(Config(workers=1, queue_capacity=1, window_ticks=2, deadline_ticks=2))
    service.advance((job(work=4), job(work=4)))
    assert service.metrics()["recovery_count"] == 1
    assert service.metrics()["recovery_ticks_sum"] == 2
    assert service.metrics()["recovery_pending"] == 0
