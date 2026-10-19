"""Checkpoints, inference, fallback and data hygiene of the seven specialist models."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from specialists.data.datasets import BUILDERS, CORPUS_TASKS, digest
from specialists.features import featurize
from specialists.model import CHECKPOINT_ROOT, CheckpointError, SpecialistModel
from specialists.runtime import AGENTS, Specialists

RESULTS = Path(__file__).resolve().parent.parent / "specialists" / ".." / "results"


@pytest.mark.parametrize("agent", AGENTS)
def test_every_agent_has_a_hash_verified_versioned_checkpoint(agent):
    m = SpecialistModel.load(CHECKPOINT_ROOT / agent)
    man = m.manifest
    assert man["agent"] == agent and man["version"] == "1.1.0"
    assert man["model_id"].startswith(f"ari-{agent}-")
    assert len(man["weights_sha256"]) == 64 and man["dataset"]["sha256"]
    assert man["evaluation"]["promoted"] in (True, False)
    if not man["evaluation"]["promoted"]:
        assert man["fallback"]["table"] or man["fallback"]["default"], "an unpromoted model must ship the baseline the runtime uses instead"


def test_tampered_weights_are_refused(tmp_path):
    shutil.copytree(CHECKPOINT_ROOT / "verify", tmp_path / "verify")
    blob = bytearray((tmp_path / "verify" / "weights.bin").read_bytes())
    blob[100] ^= 0xFF
    (tmp_path / "verify" / "weights.bin").write_bytes(bytes(blob))
    with pytest.raises(CheckpointError, match="does not match"):
        SpecialistModel.load(tmp_path / "verify")
    assert Specialists(root=tmp_path).advise("verify", {"diff": "", "tests": ""}).source == "unavailable"


def test_unpromoted_model_answers_from_its_recorded_baseline():
    sp = Specialists()
    for agent in AGENTS:
        if not sp.manifest(agent)["evaluation"]["promoted"]:
            a = sp.advise(agent, {"code": "x = 1", "cwe": "CWE-639"})
            assert a.source.startswith("baseline:"), a
            assert a.reason and "did not beat" in a.reason


def test_features_are_deterministic_and_per_field_normalised():
    a = featurize([("code", "db.execute(f\"SELECT * FROM t WHERE id = '{x}'\")"), ("cwe", "CWE-89")], 4096)
    b = featurize([("code", "db.execute(f\"SELECT * FROM t WHERE id = '{x}'\")"), ("cwe", "CWE-89")], 4096)
    assert a == b
    assert abs(sum(v * v for v in a.values()) - 1.0) < 0.25  # two unit fields scaled by 1/sqrt(2)


def test_scout_recognises_textbook_sinks_and_their_fixes():
    sp = Specialists()
    vuln = '@app.post("/restore")\ndef restore(body: Blob):\n    return pickle.loads(base64.b64decode(body.data))\n'
    fixed = '@app.post("/restore")\ndef restore(body: Blob):\n    return State.model_validate_json(base64.b64decode(body.data))\n'
    assert sp.advise("scout", {"code": vuln}).top == "CWE-502"
    assert (sp.advise("scout", {"code": fixed}).score("safe") or 0) > (sp.advise("scout", {"code": vuln}).score("safe") or 0)


@pytest.mark.parametrize("agent", CORPUS_TASKS)
def test_test_split_shares_no_code_family_with_training(agent):
    data = BUILDERS[agent]()
    train = {r["family"] for r in data["train"]} | {r["family"] for r in data["val"]}
    assert not train & {r["family"] for r in data["test"]}


@pytest.mark.parametrize("agent", ["trace", "fortify"])
def test_mitre_splits_share_no_cwe_or_parent_technique(agent):
    data = BUILDERS[agent]()
    assert not {r["family"] for r in data["train"]} & {r["family"] for r in data["test"]}


@pytest.mark.parametrize("agent", AGENTS)
def test_datasets_are_reproducible_and_match_the_checkpoint(agent):
    assert digest(BUILDERS[agent]()) == SpecialistModel.load(CHECKPOINT_ROOT / agent).manifest["dataset"]["sha256"]


@pytest.mark.parametrize("agent", AGENTS)
def test_published_results_match_the_checkpoint(agent):
    r = json.loads((RESULTS / f"{agent}.json").read_text())
    ev = SpecialistModel.load(CHECKPOINT_ROOT / agent).manifest["evaluation"]
    assert r["model_scores"][r["primary_metric"]] == ev["test"]
    assert r["promoted"] == ev["promoted"]
    assert r["inference"]["numpy_parity_argmax"] == 1.0
