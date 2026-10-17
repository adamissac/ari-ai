"""rl_defense.contracts must BE shared.rl (re-exports), and real payloads must validate."""

import json
from pathlib import Path

import shared.rl as shared_rl

import rl_defense
import rl_defense.contracts as contracts

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures/defense_recommendation.example.json"
MODELS = (
    "NodeSignals",
    "PlatformFacts",
    "ActionScore",
    "DefenseRecommendation",
    "RLCheckpointRef",
    "RLEvaluation",
    "FeatureContribution",
    "RLExplanation",
)


def test_contracts_are_reexports_not_copies():
    for name in MODELS:
        assert getattr(contracts, name) is getattr(shared_rl, name), name


def test_package_caveat_matches_shared_default():
    assert rl_defense.SIMULATION_CAVEAT == shared_rl.SIMULATION_CAVEAT_DEFAULT


def test_real_example_fixture_validates_against_shared():
    ex = json.loads(FIXTURE.read_text())
    shared_rl.PlatformFacts.model_validate(ex["input_facts"])
    rec = shared_rl.DefenseRecommendation.model_validate(ex["recommendation"])
    shared_rl.RLCheckpointRef.model_validate(ex["checkpoint"])
    expl = shared_rl.RLExplanation.model_validate(ex["explanation"])
    assert expl.recommendation_id == rec.id
