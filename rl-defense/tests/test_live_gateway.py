"""Real-enforcement and real-telemetry tests for the live loop's lower layers.

No DQN here: these prove that each permitted defensive action has a real, measured
effect on the owned demo app, and that telemetry is derived from real HTTP outcomes.
"""

from __future__ import annotations

import pytest
from payments_lite.app import create_app

from rl_defense.live.adversary import TrafficDriver
from rl_defense.live.contracts import DefenseControls
from rl_defense.live.gateway import DefensiveGateway
from rl_defense.live.telemetry import build_facts
from rl_defense.live.topology import load_topology


@pytest.fixture
def topo():
    return load_topology()


def _run(controls: DefenseControls, topo, seed: int = 1) -> DefensiveGateway:
    gw = DefensiveGateway(create_app(), topo, controls)
    TrafficDriver(seed=seed).run_window(gw)
    return gw


def test_topology_classifies_routes(topo):
    assert topo.node_for("GET", "/payments/pay_a1") == "payments"
    assert topo.node_for("GET", "/payments") == "payments"
    assert topo.node_for("GET", "/me") == "api"
    assert topo.node_for("GET", "/health") == "gateway"


def test_bola_is_real_without_defense(topo):
    """With no defense the planted BOLA really lets the attacker read another tenant."""
    gw = _run(DefenseControls(), topo)
    attack = [r for r in gw.records if r.is_attack]
    gw.close()
    assert attack, "driver should emit attack traffic"
    assert all(r.status == 200 for r in attack)
    assert all(r.compromised for r in attack)  # verified cross-tenant 200, not assumed


def test_isolate_blocks_attacker_for_real(topo):
    """Isolating payments drops every attack to 503 and compromises nothing."""
    gw = _run(DefenseControls(isolated={"payments": True}), topo)
    attack = [r for r in gw.records if r.is_attack]
    gw.close()
    assert all(r.status == 503 and r.blocked_reason == "isolated" for r in attack)
    assert sum(r.compromised for r in attack) == 0


def test_isolate_payments_disrupts_benign_payments_but_not_api(topo):
    """Isolation is not free: benign /payments reads are blocked, /me (api node) is not."""
    gw = _run(DefenseControls(isolated={"payments": True}), topo)
    benign = [r for r in gw.records if not r.is_attack]
    blocked_pay = [r for r in benign if r.node == "payments" and not r.allowed]
    api_reads = [r for r in benign if r.node == "api"]
    gw.close()
    assert blocked_pay, "some benign payments traffic should be disrupted"
    assert api_reads and all(r.allowed for r in api_reads)


def test_rate_limit_reduces_but_does_not_eliminate_compromise(topo):
    """Rate limiting throttles the attack: strictly fewer compromises than no defense,
    strictly more than full isolation."""
    none = _run(DefenseControls(), topo)
    rl = _run(DefenseControls(rate_limited={"payments": True}, rate_limit_allow_every=3), topo)
    iso = _run(DefenseControls(isolated={"payments": True}), topo)
    c_none = sum(r.compromised for r in none.records if r.is_attack)
    c_rl = sum(r.compromised for r in rl.records if r.is_attack)
    c_iso = sum(r.compromised for r in iso.records if r.is_attack)
    for gw in (none, rl, iso):
        gw.close()
    assert c_iso < c_rl < c_none


def test_raise_monitoring_sharpens_detection_without_disruption(topo):
    """Higher monitoring raises the measured anomaly_score (detection) and blocks nothing."""
    base = _run(DefenseControls(monitoring_level={"payments": 0}), topo)
    hi = _run(DefenseControls(monitoring_level={"payments": 2}), topo)

    def anomaly(gw, ctrl):
        facts = build_facts(
            gw.records, ctrl, topo, finding_severity={"payments": 0.8}, step=1, horizon=30,
            escalations_used=0, max_escalations=3, escalation_pending=False,
        )
        return next(n.anomaly_score for n in facts.nodes if n.node == "payments")

    a0 = anomaly(base, DefenseControls(monitoring_level={"payments": 0}))
    a2 = anomaly(hi, DefenseControls(monitoring_level={"payments": 2}))
    assert a2 > a0
    assert all(r.allowed for r in hi.records)  # monitoring never blocks traffic
    base.close()
    hi.close()


def test_telemetry_alert_rate_tracks_attack_volume(topo):
    """More attack traffic → higher measured alert_rate on the payments node."""

    def alert(attack_per_step: int) -> float:
        gw = DefensiveGateway(create_app(), topo, DefenseControls())
        TrafficDriver(seed=1, benign_per_step=4, attack_per_step=attack_per_step).run_window(gw)
        facts = build_facts(
            gw.records, DefenseControls(), topo, finding_severity={"payments": 0.8}, step=1,
            horizon=30, escalations_used=0, max_escalations=3, escalation_pending=False,
        )
        gw.close()
        return next(n.alert_rate for n in facts.nodes if n.node == "payments")

    assert alert(10) > alert(2)
