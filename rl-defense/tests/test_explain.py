import numpy as np
import pytest
import torch
from torch import nn

from rl_defense.envs.defense_sim import N_ACTIONS, NODE_FEATURES, OBS_DIM, encode_action
from rl_defense.explain import explain


class LinearQ(nn.Module):
    """Q(a) = w_a · obs, so occlusion effects are exactly computable."""

    def __init__(self, weights):
        super().__init__()
        self.w = torch.tensor(weights, dtype=torch.float32)

    def forward(self, obs):
        return obs @ self.w.T


def _setup():
    w = np.zeros((N_ACTIONS, OBS_DIM))
    iso_payments = encode_action("isolate", 3)
    anomaly_payments = 3 * len(NODE_FEATURES) + NODE_FEATURES.index("anomaly_score")
    w[iso_payments, anomaly_payments] = 2.0  # isolating payments is driven by its anomaly
    w[0, :] = 0.1  # noop has a small value everywhere
    obs = np.zeros(OBS_DIM, dtype=np.float32)
    obs[anomaly_payments] = 0.8
    obs[0] = 0.5
    return LinearQ(w), obs, iso_payments


def test_explanation_identifies_the_driving_feature_exactly():
    net, obs, _ = _setup()
    e = explain(net, obs, np.ones(N_ACTIONS, dtype=bool))
    assert e.action == "isolate:payments" and e.runner_up == "noop"
    top = e.top_contributions[0]
    assert (top.node, top.feature, top.kind) == ("payments", "anomaly_score", "signal")
    assert top.delta_margin == pytest.approx(2.0 * 0.8 - 0.1 * 0.8, abs=1e-4)
    assert e.margin == pytest.approx(1.6 + 0.0 - 0.1 * 1.3, abs=1e-4)


def test_explanation_respects_mask_and_skips_zero_features():
    net, obs, iso = _setup()
    mask = np.ones(N_ACTIONS, dtype=bool)
    mask[iso] = False
    e = explain(net, obs, mask)
    assert e.action != "isolate:payments"
    assert all(c.value != 0.0 for c in e.top_contributions)


def test_explanation_is_deterministic_and_validates_input():
    net, obs, _ = _setup()
    mask = np.ones(N_ACTIONS, dtype=bool)
    assert explain(net, obs, mask) == explain(net, obs, mask)
    with pytest.raises(ValueError):
        explain(net, obs[:-1], mask)
    with pytest.raises(ValueError):
        explain(net, obs, np.zeros(N_ACTIONS, dtype=bool))
