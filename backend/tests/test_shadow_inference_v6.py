"""The frozen v6 checkpoint really runs in the shadow path, and fails safe.

The other live-defense tests accept either outcome (``if decision["inference_ran"]``), so
none of them proves the trained policy produces a recommendation. These run the committed,
hash-pinned checkpoint on simulated owned-staging windows and check the recommendation
against an independent load of the same weights. Nothing here executes a control.
"""

from __future__ import annotations

import pytest

# The plain backend environment has no numpy/torch/rl_defense; the rl-integration job does
# and fails on any skip.
np = pytest.importorskip("numpy")
pytest.importorskip("torch")
pytest.importorskip("rl_defense")

from backend.live_defense import policy  # noqa: E402
from backend.live_defense.policy import (  # noqa: E402
    V6_OBS_DIM,
    V6_SHA256,
    decide_inference,
    pick_rule_action,
)
from monitoring.detect import WindowView, authorization_context, detect  # noqa: E402
from shared.base import utcnow  # noqa: E402
from shared.live_defense import AuthorizationContext, InferenceStatus  # noqa: E402
from shared.monitoring import PrincipalCounts  # noqa: E402

N_FEATURES = 9  # per node, in NODE order gateway, api, auth, payments, db
ALERT, ANOMALY = 0, 1
AUTH, PAYMENTS = 2, 3
BLOCKS = {"block_principal", "block_principal_long", "block_top_principal_long"}


def _view(route: str, requests: int, *, s4: int = 0, af: int = 0, principals=(), score=0.0):
    return WindowView(
        route=route,
        requests=requests,
        status_4xx=s4,
        status_5xx=0,
        auth_failures=af,
        principals=tuple(principals),
        anomaly_score=score,
        source="owned_staging",
        successes=requests - s4,
    )


def _bola() -> list[WindowView]:
    return [
        _view(
            "GET /payments/{id}",
            20,
            principals=[
                PrincipalCounts(principal="prn_mallory1", cross_tenant=8, own=2),
                PrincipalCounts(principal="prn_alice001", own=10),
            ],
            score=0.6,
        )
    ]


def _decide(windows: list[WindowView]):
    return decide_inference(
        source="owned_staging",
        windows=windows,
        hits=detect(windows),
        auth=authorization_context(windows),
        window_end=utcnow(),
    )


@pytest.fixture(autouse=True)
def _fresh_runner(monkeypatch):
    monkeypatch.setattr(policy, "_RUNNER", None)


def test_v6_recommends_from_a_simulated_cross_tenant_window_and_is_traceable():
    from rl_defense.checkpoint import load_checkpoint

    windows = _bola()
    assert authorization_context(windows) is AuthorizationContext.verified
    out = _decide(windows)
    assert out.status is InferenceStatus.ran and out.reason is None
    assert out.checkpoint_sha256 == V6_SHA256
    assert out.policy_version == f"LiveDefense-payments-lite-v3@{V6_SHA256[:12]}"
    assert out.feature_schema_ok and out.action_mask_valid
    obs = np.asarray(out.observation, dtype=np.float32)
    assert obs.shape == (V6_OBS_DIM,) and obs.min() >= 0.0 and obs.max() <= 1.0
    # the observation is the input window: 8 cross-tenant reads on the payments node
    assert obs[PAYMENTS * N_FEATURES + ALERT] == pytest.approx(0.8)
    assert obs[PAYMENTS * N_FEATURES + ANOMALY] == pytest.approx(0.6)
    assert out.action in BLOCKS and out.principal_targets == ["prn_mallory1"]

    # An independent load of the same bytes gives the same Q-values for that observation.
    agent, manifest = load_checkpoint(policy.V6_CHECKPOINT)
    assert manifest["checkpoint_sha256"] == V6_SHA256
    q = agent.q_values(obs)
    scores = [s.q_value for s in out.top_actions]
    assert scores == sorted(scores, reverse=True)
    by_action = {(s.action, s.node): s.q_value for s in out.top_actions}
    assert all(np.isclose(q, v, atol=1e-6).any() for v in by_action.values())
    assert by_action[(out.action, out.node)] == pytest.approx(scores[0])
    assert out.q_margin == pytest.approx(scores[0] - scores[1], abs=1e-6)


def test_v6_is_deterministic_across_a_runner_reload(monkeypatch):
    first = _decide(_bola())
    monkeypatch.setattr(policy, "_RUNNER", None)  # as after a process restart
    second = _decide(_bola())
    assert first.status is second.status is InferenceStatus.ran
    assert (first.action, first.node, first.observation, first.q_margin) == (
        second.action,
        second.node,
        second.observation,
        second.q_margin,
    )
    assert [s.q_value for s in first.top_actions] == [s.q_value for s in second.top_actions]


def test_error_responses_are_counted_once_like_the_lab_detector():
    # 3 of 10 login requests fail with 401 (inside status_4xx) and one principal makes a
    # cross-tenant read. The lab detector v6 trained on counts 1 + 3 = 4 anomalous requests.
    windows = [
        _view(
            "POST /auth/login",
            10,
            s4=3,
            af=3,
            principals=[PrincipalCounts(principal="prn_mallory1", cross_tenant=1, own=2)],
        )
    ]
    out = _decide(windows)
    assert out.status is InferenceStatus.ran
    assert out.observation[AUTH * N_FEATURES + ALERT] == pytest.approx(0.4)


@pytest.mark.parametrize("damage", ["tampered", "missing"])
def test_unusable_checkpoint_abstains_and_the_rules_stand(tmp_path, monkeypatch, damage):
    path = tmp_path / "candidate_online.pt"
    if damage == "tampered":
        blob = bytearray(policy.V6_CHECKPOINT.read_bytes())
        blob[len(blob) // 2] ^= 0xFF
        path.write_bytes(bytes(blob))
    monkeypatch.setattr(policy, "V6_CHECKPOINT", path)
    windows = _bola()
    out = _decide(windows)
    assert out.status is InferenceStatus.skipped_unavailable
    assert out.action is None and out.top_actions is None and out.observation is None
    assert out.policy_version is None and out.checkpoint_sha256 is None
    # the deterministic rule suggestion is what the engine records instead
    assert pick_rule_action(detect(windows))[0] == "block_principal"


def test_checkpoint_swapped_after_load_is_refused(tmp_path, monkeypatch):
    assert _decide(_bola()).status is InferenceStatus.ran  # runner now cached
    swapped = tmp_path / "candidate_online.pt"
    swapped.write_bytes(policy.V6_CHECKPOINT.read_bytes() + b"\0")
    monkeypatch.setattr(policy, "V6_CHECKPOINT", swapped)
    assert _decide(_bola()).status is InferenceStatus.skipped_unavailable


def test_unverified_or_off_topology_traffic_never_reaches_the_model():
    anonymous = [_view("GET /payments/{id}", 20, score=0.9)]
    out = _decide(anonymous)
    assert out.status is InferenceStatus.skipped_authorization and out.action is None
    foreign = [
        _view(
            "GET /orders/{id}",
            20,
            principals=[PrincipalCounts(principal="prn_mallory1", cross_tenant=8, own=2)],
            score=0.6,
        )
    ]
    out = _decide(foreign)
    assert out.status is InferenceStatus.skipped_schema and out.action is None
    for source in ("simulated", "replay", "drill"):  # synthetic counters are not telemetry
        synthetic = decide_inference(
            source=source,
            windows=_bola(),
            hits=detect(_bola()),
            auth=AuthorizationContext.verified,
            window_end=utcnow(),
        )
        assert synthetic.status is InferenceStatus.skipped_source and synthetic.action is None
