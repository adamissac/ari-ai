from pathlib import Path

import pytest

from rl_defense.envs.defense_sim import OBS_DIM
from rl_defense.observations import from_platform_facts, mask_from_facts
from rl_defense.platform_mapping import (
    DefenseState,
    ExpectationInput,
    FindingInput,
    RouteSignal,
    facts_from_platform,
    load_topology,
)

TOPOLOGY = load_topology(
    Path(__file__).resolve().parents[1] / "configs/topology/payments_lite.yaml"
)
AUTHZ = FindingInput(
    id="fnd_authz", status="validated", severity="high", routes=("GET /payments/{payment_id}",)
)


def node(facts, name):
    return next(n for n in facts.nodes if n.node == name)


def test_routes_map_to_nodes():
    assert TOPOLOGY.node_for_route("GET /payments/{payment_id}") == "payments"
    assert TOPOLOGY.node_for_route("POST /refunds") == "payments"
    assert TOPOLOGY.node_for_route("POST /auth/login") == "auth"
    assert TOPOLOGY.node_for_route("GET /unknown") == "api"  # default node


def test_validated_finding_raises_node_severity_with_provenance():
    facts, prov = facts_from_platform(TOPOLOGY, [AUTHZ], [])
    assert node(facts, "payments").finding_severity == 0.75
    assert "fnd_authz" in prov["payments"]
    assert all(node(facts, n).finding_severity == 0.0 for n in ("gateway", "api", "auth", "db"))


@pytest.mark.parametrize(
    "status", ["hypothesis", "refuted", "inconclusive", "verified", "closed", "hardened"]
)
def test_unvalidated_or_fixed_findings_do_not_count(status):
    f = AUTHZ.model_copy(update={"status": status})
    facts, _ = facts_from_platform(TOPOLOGY, [f], [])
    assert node(facts, "payments").finding_severity == 0.0


def test_accepted_risk_still_counts_as_open_exposure():
    f = AUTHZ.model_copy(update={"status": "accepted_risk"})
    facts, _ = facts_from_platform(TOPOLOGY, [f], [])
    assert node(facts, "payments").finding_severity == 0.75


def test_status_vocabulary_matches_docs12():
    from rl_defense.platform_mapping import OPEN_VALIDATED_STATUSES

    docs12 = {
        "hypothesis",
        "validated",
        "refuted",
        "inconclusive",
        "diagnosed",
        "patch_proposed",
        "verified",
        "patch_rejected",
        "unresolved",
        "hardened",
        "accepted_risk",
        "closed",
        "needs_recheck",
    }
    assert OPEN_VALIDATED_STATUSES <= docs12
    assert not OPEN_VALIDATED_STATUSES & {
        "hypothesis",
        "refuted",
        "inconclusive",
        "verified",
        "hardened",
        "closed",
    }


def test_max_severity_wins_per_node():
    low = FindingInput(id="fnd_low", status="diagnosed", severity="low", routes=("POST /refunds",))
    facts, _ = facts_from_platform(TOPOLOGY, [low, AUTHZ], [])
    assert node(facts, "payments").finding_severity == 0.75


def test_expectation_sensitivity_sets_criticality_and_rejected_is_ignored():
    exps = [
        ExpectationInput(
            id="exp_own", route="GET /me", data_sensitivity="financial", status="confirmed"
        ),
        ExpectationInput(
            id="exp_rej", route="POST /auth/login", data_sensitivity="financial", status="rejected"
        ),
    ]
    facts, prov = facts_from_platform(TOPOLOGY, [], exps)
    assert node(facts, "api").criticality == 0.9 and "exp_own" in prov["api"]
    assert node(facts, "auth").criticality == 0.7  # floor only; rejected expectation ignored


def test_signals_and_defense_state_flow_into_observation_and_mask():
    sig = [
        RouteSignal(
            route="GET /payments/{payment_id}",
            alert_rate=6.0,
            anomaly_score=0.6,
            source="runtime_demo",
        )
    ]
    facts, _ = facts_from_platform(
        TOPOLOGY, [AUTHZ], [], sig, DefenseState(isolated=frozenset({"payments"}))
    )
    p = node(facts, "payments")
    assert (p.alert_rate, p.anomaly_score, p.isolated) == (6.0, 0.6, True)
    obs = from_platform_facts(facts)
    assert obs.shape == (OBS_DIM,) == (48,)
    from rl_defense.envs.defense_sim import encode_action

    mask = mask_from_facts(facts)
    assert not mask[encode_action("isolate", 3)] and not mask[encode_action("rate_limit", 3)]


def test_verified_fix_changes_policy_input():
    open_facts, _ = facts_from_platform(TOPOLOGY, [AUTHZ], [])
    fixed_facts, _ = facts_from_platform(
        TOPOLOGY, [AUTHZ.model_copy(update={"status": "verified"})], []
    )
    assert (from_platform_facts(open_facts) != from_platform_facts(fixed_facts)).any()
