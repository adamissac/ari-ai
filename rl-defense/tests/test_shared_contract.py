"""Consumer contract test: local RL DTOs must match shared/ V0 (owner: Srihith).

Runs when the ``shared`` package is importable (installed, or SHARED_PATH points at
the repo's ``shared/`` directory); skipped otherwise. Once shared/ V0 merges,
``rl_defense.contracts`` will re-export from ``shared.rl`` and this test keeps the
two from drifting until then.
"""

import json
import os
import sys
from pathlib import Path

import pytest

if os.environ.get("SHARED_PATH"):
    sys.path.insert(0, os.environ["SHARED_PATH"])
shared_rl = pytest.importorskip("shared.rl", reason="shared/ V0 not available in this checkout")

import rl_defense.contracts as local  # noqa: E402

MODELS = ("NodeSignals", "PlatformFacts", "ActionScore", "DefenseRecommendation", "RLCheckpointRef")
FIXTURE = Path(__file__).resolve().parents[1] / "fixtures/defense_recommendation.example.json"


def _shape(model):
    schema = model.model_json_schema()
    return {
        name: (prop.get("type"), prop.get("enum"), prop.get("const"), prop.get("pattern"))
        for name, prop in schema.get("properties", {}).items()
    }


@pytest.mark.parametrize("name", MODELS)
def test_field_names_and_types_match_shared(name):
    assert _shape(getattr(local, name)) == _shape(getattr(shared_rl, name))


def test_real_recommendation_fixture_validates_against_shared():
    ex = json.loads(FIXTURE.read_text())
    shared_rl.PlatformFacts.model_validate(ex["input_facts"])
    shared_rl.DefenseRecommendation.model_validate(ex["recommendation"])
    shared_rl.RLCheckpointRef.model_validate(ex["checkpoint"])
