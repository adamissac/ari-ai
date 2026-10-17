"""Adam's integration gap (20261017T063710Z-adam-to-all-integration-gaps): persisted
expectations from Sarosh's real index of payments-lite feed RL criticality through
backend.pipeline.platform_facts, and a human "rejected" decision removes their influence."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ci_api = pytest.importorskip("code_intelligence.api")
ci_persistence = pytest.importorskip("code_intelligence.persistence")
pm = pytest.importorskip("rl_defense.platform_mapping")

from helpers import REPO, setup_project  # noqa: E402

from backend.db import transaction  # noqa: E402
from backend.intel_store import PostgresPayloadStore  # noqa: E402
from backend.pipeline import platform_facts, route_expectations  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "examples" / "payments-lite" / "target"
TOPOLOGY = ROOT / "rl-defense" / "configs" / "topology" / "payments_lite.yaml"


@pytest.fixture
def indexed(client_factory, tmp_path: Path):
    if not TARGET.exists():
        pytest.skip("examples/payments-lite/target not present")
    root = tmp_path / "payments-lite"
    shutil.copytree(TARGET, root, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    git = ["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@example.invalid"]
    subprocess.check_call([*git, "init", "-q"])
    subprocess.check_call([*git, "add", "."])
    subprocess.check_call([*git, "-c", "commit.gpgsign=false", "commit", "-qm", "base"])
    sha = subprocess.check_output([*git, "rev-parse", "HEAD"], text=True).strip()
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)
    binding = ci_api.RepositoryBinding(
        project_id=ids["project"], repo_id=ids["repo"], full_name=REPO, local_path=root
    )
    svc = ci_api.IntelligenceService(
        ci_persistence.PayloadIndexStore(PostgresPayloadStore()), [binding]
    )
    ref = svc.index_repository(ids["project"], ids["repo"], sha)
    return alice, ids, ref


def _node(facts, name):
    return next(n for n in facts.nodes if n.node == name)


def test_expectations_raise_rl_criticality_from_real_index(indexed, settings_override) -> None:
    alice, ids, ref = indexed
    settings_override(rl_topology_path=str(TOPOLOGY))
    with transaction() as conn:
        exps = route_expectations(conn, ids["project"])
        facts, provenance = platform_facts(conn, ids["project"])
    by_route = {}
    for e in exps:
        by_route.setdefault(e["route"], []).append(e)
    assert len({e["id"] for e in exps}) == len(exps)
    # the planted IDOR route carries financial expectations from the real index
    assert {e["data_sensitivity"] for e in by_route["GET /payments/{payment_id}"]} == {"financial"}
    payments = {
        e["id"]
        for r, es in by_route.items()
        if r.split()[1].startswith(("/payments", "/refunds"))
        for e in es
    }
    assert payments and payments <= set(provenance["payments"])
    # /health has an "internal" expectation: gateway criticality rises above its 0.3 floor
    health = [e["id"] for e in by_route["GET /health"]]
    assert _node(facts, "gateway").criticality == pytest.approx(0.4)
    assert set(health) <= set(provenance["gateway"])

    # A human "rejected" decision (authenticated API) removes that expectation's influence.
    for exp_id in health:
        r = alice.patch(
            f"/api/v1/snapshots/{ref.snapshot_id}/expectations/{exp_id}",
            json={
                "status": "rejected",
                "reason": "Health probe holds no data",
                "expected_revision": 0,
            },
        )
        assert r.status_code == 200, r.text
    with transaction() as conn:
        assert all(
            e["status"] == "rejected"
            for e in route_expectations(conn, ids["project"])
            if e["id"] in health
        )
        facts, provenance = platform_facts(conn, ids["project"])
    assert _node(facts, "gateway").criticality == pytest.approx(0.3)
    assert not set(health) & set(provenance["gateway"])


def test_no_index_means_topology_floors(client_factory, settings_override) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)
    settings_override(rl_topology_path=str(TOPOLOGY))
    with transaction() as conn:
        assert route_expectations(conn, ids["project"]) == []
        facts, _ = platform_facts(conn, ids["project"])
    assert _node(facts, "gateway").criticality == pytest.approx(0.3)
