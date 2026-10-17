"""RL facts use code-intelligence expectations: data sensitivity raises node criticality.

This is the P1→P3 link (docs/11): an expectation that a route handles financial data
makes the simulator node behind that route more critical in the policy's input.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
import sqlalchemy as sa

pytest.importorskip("rl_defense.platform_mapping")

from helpers import setup_project  # noqa: E402

from backend import intelligence as intel  # noqa: E402
from backend import pipeline  # noqa: E402
from backend.db import snapshots, transaction  # noqa: E402
from shared.base import utcnow  # noqa: E402
from shared.ids import IdPrefix, new_id  # noqa: E402

TOPOLOGY = Path(__file__).resolve().parents[2] / "rl-defense/configs/topology/payments_lite.yaml"


class _FakeIntel:
    """Duck-typed stand-in for IntelligenceService (only the two read calls RL uses)."""

    def __init__(self, entry_points, expectations, fail=False):
        self._eps, self._exps, self._fail = entry_points, expectations, fail

    def _page(self, items, offset, limit):
        if self._fail:
            raise RuntimeError("store offline")
        return items[offset : offset + limit]

    def entry_points(self, ref, *, offset=0, limit=100):
        return self._page(self._eps, offset, limit)

    def expectations(self, ref, subject=None, *, offset=0, limit=100):
        return self._page(self._exps, offset, limit)


def _ns_enum(value):
    return SimpleNamespace(value=value)


def _exp(id_, subject, sensitivity, status="confirmed"):
    return SimpleNamespace(
        id=id_,
        subject_ref=subject,
        data_sensitivity=None if sensitivity is None else _ns_enum(sensitivity),
        status=_ns_enum(status),
    )


def _ready_snapshot(repo_id: str) -> str:
    sid = new_id(IdPrefix.snp)
    with transaction() as conn:
        conn.execute(
            sa.insert(snapshots).values(
                id=sid,
                repo_id=repo_id,
                commit_sha="c" * 40,
                index_version="test",
                status="ready",
                doc={},
                created_at=utcnow(),
            )
        )
    return sid


def _facts(project_id):
    with transaction() as conn:
        return pipeline.platform_facts(conn, project_id)


def _node(facts, name):
    return next(n for n in facts.nodes if n.node == name)


@pytest.fixture
def project(client_factory, settings_override):
    settings_override(rl_topology_path=str(TOPOLOGY))
    alice, bob = client_factory("alice"), client_factory("bob")
    return setup_project(alice, bob)


def test_financial_expectation_raises_criticality_with_provenance(project, monkeypatch):
    _ready_snapshot(project["repo"])
    eps = [
        SimpleNamespace(id="ent_me", handler_symbol_id="sym_me", method="GET", path_template="/me"),
    ]
    exps = [
        _exp("exp_fin", "sym_me", "financial"),  # subject is the handler symbol
        _exp("exp_rej", "ent_me", "financial", status="rejected"),
        _exp("exp_none", "ent_me", None),
    ]
    monkeypatch.setattr(intel, "build_service", lambda: _FakeIntel(eps, exps))
    monkeypatch.setattr(intel, "snapshot_ref", lambda sid: SimpleNamespace(snapshot_id=sid))
    facts, provenance = _facts(project["project"])
    assert _node(facts, "api").criticality == 0.9  # floor 0.5 -> financial 0.9
    assert "exp_fin" in provenance["api"]
    assert "exp_rej" not in provenance["api"] and "exp_none" not in provenance["api"]
    assert provenance["expectations_source"].startswith("1 expectation-route inputs")


def test_intelligence_outage_falls_back_to_topology_floor(project, monkeypatch):
    _ready_snapshot(project["repo"])
    monkeypatch.setattr(intel, "build_service", lambda: _FakeIntel([], [], fail=True))
    monkeypatch.setattr(intel, "snapshot_ref", lambda sid: SimpleNamespace(snapshot_id=sid))
    facts, provenance = _facts(project["project"])
    assert _node(facts, "api").criticality == 0.5
    assert provenance["expectations_source"] == "intelligence unavailable: RuntimeError"


def test_no_ready_snapshot_is_reported(project):
    facts, provenance = _facts(project["project"])
    assert _node(facts, "api").criticality == 0.5
    assert provenance["expectations_source"] == "no ready snapshot"
