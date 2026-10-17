"""RL-005 acceptance: a defense recommendation is stored with its caveat and nothing in the
API can apply it. The policy is decision support from a simulator; isolating or rate-limiting
a real service stays a human action outside this platform."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from backend.main import create_app
from shared.rl import SIMULATION_CAVEAT_DEFAULT, DefenseRecommendation

# Words a route would need in its path to act on a recommendation or a defended system.
ACTION_WORDS = ("apply", "execute", "enact", "isolate", "rate-limit", "rate_limit", "contain")


def _operations() -> list[tuple[str, str]]:
    """(METHOD, path) for every operation in the API schema. The one route hidden from the
    schema is the incident transition alias (``/incidents/{incident_id}/transition``), which
    does not touch recommendations or defended systems."""
    paths = create_app().openapi()["paths"]
    return [(method.upper(), path) for path, item in paths.items() for method in item]


def test_recommendation_routes_are_read_only_except_the_enqueue() -> None:
    operations = _operations()
    assert any("defense-recommendation" in path for _, path in operations)
    writes = sorted(
        (method, path)
        for method, path in operations
        if "defense-recommendation" in path and method not in {"GET", "HEAD", "OPTIONS"}
    )
    # The only write asks the worker to compute a new recommendation; it changes no system.
    assert writes == [("POST", "/api/v1/projects/{project_id}/defense-recommendations")]


def test_no_route_applies_a_defensive_action() -> None:
    offending = [
        path for _, path in _operations() if any(word in path.lower() for word in ACTION_WORDS)
    ]
    assert offending == []


def _recommendation(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "id": "rec_" + "0" * 26,
        "project_id": None,
        "policy_version": "DefenseSimEnv-v0@abcdef12",
        "checkpoint_sha256": "a" * 64,
        "action": "isolate",
        "node": "api",
        "q_margin": 0.4,
        "top_actions": [],
        "observation": [0.0] * 48,
        "created_at": datetime(2026, 10, 17, tzinfo=UTC),
    }
    base.update(overrides)
    return base


def test_recommendation_carries_the_simulation_caveat_by_default() -> None:
    rec = DefenseRecommendation.model_validate(_recommendation())
    assert rec.simulation_derived is True
    assert rec.caveat == SIMULATION_CAVEAT_DEFAULT
    assert "never executed automatically" in rec.caveat


def test_recommendation_cannot_claim_to_be_real() -> None:
    with pytest.raises(ValidationError):
        DefenseRecommendation.model_validate(_recommendation(simulation_derived=False))
