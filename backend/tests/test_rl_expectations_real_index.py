"""Complements test_rl_expectations.py (stubbed service) with Sarosh's REAL index of the
payments-lite target persisted in PostgreSQL: expectations reach RL criticality through
backend.pipeline.platform_facts, and an authenticated "rejected" decision removes them."""

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
from backend.pipeline import platform_facts  # noqa: E402

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


def _exp_ids(provenance, node):
    return {p for p in provenance[node] if p.startswith("exp_")}


def test_real_index_expectations_raise_rl_criticality(indexed, settings_override) -> None:
    alice, ids, ref = indexed
    settings_override(rl_topology_path=str(TOPOLOGY))
    with transaction() as conn:
        facts, provenance = platform_facts(conn, ids["project"])
    assert "from 1 snapshot(s)" in provenance["expectations_source"]
    # payments-lite's /payments* and /refunds routes carry financial expectations
    assert _exp_ids(provenance, "payments")
    # /health has "internal" expectations: gateway rises above its 0.3 floor
    health = _exp_ids(provenance, "gateway")
    assert health and _node(facts, "gateway").criticality == pytest.approx(0.4)

    # A human "rejected" decision (authenticated API) removes their influence.
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
        facts, provenance = platform_facts(conn, ids["project"])
    assert _node(facts, "gateway").criticality == pytest.approx(0.3)
    assert not _exp_ids(provenance, "gateway")
    assert _exp_ids(provenance, "payments")
