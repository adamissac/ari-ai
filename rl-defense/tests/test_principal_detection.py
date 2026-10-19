"""Runtime principal detection (contracts 0.14): the lab gateway as a reporter, and the
platform mapping that turns its counters into live v3 PlatformFacts.

The key property: for one window of real requests through the defensive gateway, the
fields the *platform* computes from the reporter's aggregated, pseudonymous counters equal
the fields the *lab loop* computes from its own records, so a live_v3 policy sees the same
observation in the product as in the lab (when no block is in force; the platform enforces
none).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from rl_defense import layouts as lay
from rl_defense import platform_mapping as pm
from rl_defense.envs.defense_sim import NOOP_ACTION
from rl_defense.live import evaluate as ev
from rl_defense.live import report
from rl_defense.live.adversary import live_app
from rl_defense.live.loop import LiveDefenseLoop, LoopConfig
from rl_defense.live.scenarios import SEED_BANDS, LiveScenario
from rl_defense.observations import from_platform_facts, mask_from_facts

KEY = b"reporter-only-test-key"
T0 = datetime(2026, 10, 19, tzinfo=UTC)
TOPO = pm.load_topology(
    pm.Path(__file__).resolve().parents[1] / "configs/topology/payments_lite.yaml"
)
PRINCIPAL_FIELDS = (
    "principal_block_available",
    "principal_block_long_available",
    "principal_block_top_long_available",
    *lay.LIVE_V3_DETECTOR_FEATURES,
)


def _scenario(**kw) -> LiveScenario:
    base = {
        "name": "pd",
        "split": "train",
        "schedule": "always",
        "attack_per_step": 4,
        "benign_per_step": 6,
        "attackers": ("dave", "mallory"),
        "attacker_switch": "per_request",
        "victims": ("carol",),
        "benign": ("alice", "carol", "dave"),
        "delegations": ("dave:alice",),
        "delegate_per_step": 2,
        "seed_start": SEED_BANDS["train"][0],
        "episodes": 1,
    }
    return LiveScenario(**{**base, **kw})


def _platform_side(records):  # noqa: ANN001, ANN202
    batch = report.runtime_batch(
        records, source="simulated", window_start=T0, window_end=T0 + timedelta(minutes=1), key=KEY
    )
    detections = [
        pm.RouteDetection(
            source="simulated",
            **w.model_dump(include={"route", "requests", "status_4xx", "status_5xx", "principals"}),
        )
        for w in batch.routes
    ]
    return batch, detections, pm.principal_facts(TOPO, detections)


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_platform_fields_equal_the_lab_loops_for_the_same_window(seed):
    loop = LiveDefenseLoop(
        live_app,
        config=LoopConfig(action_space="live_v3", **ev.V4_LOOP_OVERRIDES),
        driver=_scenario().driver(),
    )
    loop.reset(seed)
    for _ in range(3):  # noop: no block in force, as on the platform
        loop.step(NOOP_ACTION)
        lab = loop.platform_facts()
        _, detections, (fields, targets) = _platform_side(loop._gateway.records)
        for f in PRINCIPAL_FIELDS:
            want = getattr(lab, f)
            got = fields.get(f, type(want)())
            assert got == pytest.approx(want), f
        assert set(targets.all) == {report.pseudonym(p, KEY) for p in loop._flagged}
        assert set(targets.top) == {report.pseudonym(p, KEY) for p in loop._top}
        # node detection signals: the platform's equal the lab's on every node
        facts, _ = pm.facts_from_platform(TOPO, [], [], [], detections=detections)
        for pn, ln in zip(facts.nodes, lab.nodes, strict=True):
            assert (pn.node, pn.alert_rate) == (ln.node, ln.alert_rate)
            assert pn.anomaly_score == pytest.approx(ln.anomaly_score)
        # and therefore the live_v3 observation/mask the policy sees are identical
        plat = lab.model_copy(update=dict.fromkeys(PRINCIPAL_FIELDS, 0) | fields)
        for space in ("live_v2", "live_v3"):
            np.testing.assert_array_equal(
                from_platform_facts(plat, space=space), from_platform_facts(lab, space=space)
            )
            np.testing.assert_array_equal(
                mask_from_facts(plat, space=space), mask_from_facts(lab, space=space)
            )
    loop.close()


def test_reporter_sends_pseudonyms_and_counts_grants_as_delegated():
    loop = LiveDefenseLoop(
        live_app,
        config=LoopConfig(action_space="live_v3", **ev.V4_LOOP_OVERRIDES),
        driver=_scenario(attack_per_step=0).driver(),
    )
    loop.reset(0)
    loop.step(NOOP_ACTION)
    batch, _, (fields, targets) = _platform_side(loop._gateway.records)
    loop.close()
    raw = batch.model_dump_json()
    assert "cus_" not in raw and "fixture-token" not in raw  # no raw ids or tokens leave
    dave = report.pseudonym("cus_dave", KEY)
    pay = next(w for w in batch.routes if w.route == "GET /payments/{payment_id}")
    d = next(p for p in pay.principals if p.principal == dave)
    assert d.delegated == 2 and d.cross_tenant == 0  # authorized reads are not flagged
    assert fields == {} and targets.all == ()  # no attack: nothing flagged, no block valid


def test_no_principal_counters_keep_the_v3_defaults():
    facts, prov = pm.facts_from_platform(TOPO, [], [], [], project_id=None)
    assert not facts.principal_block_available and facts.flagged_volume == 0.0
    assert "principal_targets:all" not in prov


def test_monitoring_sensitivity_matches_the_lab_telemetry():
    from rl_defense.live import telemetry

    for level, sens in pm.MONITORING_SENSITIVITY.items():
        assert telemetry._MONITORING_SENSITIVITY[level] == sens
