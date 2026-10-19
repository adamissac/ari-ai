"""The restored v6 evidence: original bytes, hash-pinned, restorable and promotable.

Reads the committed rl-defense/results/live-retrain-v6/ directory. Never runs a policy on
any scenario and never touches a real registry (promotion is only exercised on a temporary
copy, the way the registry tests do).
"""

from __future__ import annotations

import gzip
import json
import shutil
from pathlib import Path

import pytest

from rl_defense.checkpoint import load_checkpoint
from rl_defense.inference import PolicyRunner
from rl_defense.live import evidence

V6 = Path(__file__).resolve().parents[1] / "results" / "live-retrain-v6"


def test_index_report_and_checkpoint_pin_the_same_bytes():
    idx = evidence.load_index(V6)["artifacts"]
    report = json.loads((V6 / "promotion_report.json").read_text())
    manifest = json.loads((V6 / "candidate.manifest.json").read_text())
    ck = idx["checkpoint"]["sha256"]
    assert ck == manifest["checkpoint_sha256"] == report["candidate"]["checkpoint_sha256"]
    assert idx["experiment"]["sha256"] == manifest["lineage"]["experience_sha256"]
    for name, a in report["artifacts"].items():
        src = "experiment" if name == "experience" else name
        assert (a["path"], a["sha256"]) == (idx[src]["path"], idx[src]["sha256"])
    # the sidecar the loader reads next to the checkpoint is the committed manifest
    assert (V6 / "candidate_online.manifest.json").read_bytes() == (
        V6 / "candidate.manifest.json"
    ).read_bytes()


def test_committed_evidence_verifies_by_streaming():
    """268 MB of experience, decompressed and hashed in a stream; the prefix is the
    selected snapshot's 3000 demos + 105000 online steps."""
    got = evidence.verify(V6)
    assert set(got) == {"checkpoint", "experiment", "selected_experience"}
    idx = evidence.load_index(V6)["artifacts"]
    assert idx["selected_experience"]["lines"] == 3000 + 105000


def test_original_checkpoint_loads_and_serves():
    agent, m = load_checkpoint(V6 / "candidate_online.pt")
    assert m["env_id"] == "LiveDefense-payments-lite-v3" and m["steps"] == 105_000
    assert agent.config.noop_margin == m["online"]["selected_noop_margin"] == 0.1
    assert PolicyRunner(V6 / "candidate_online.pt").policy_version.endswith("@8113a37f4ff9")


def _copy(tmp: Path) -> Path:
    d = tmp / "v6"
    d.mkdir()
    for f in (
        "EVIDENCE.json",
        "promotion_report.json",
        "candidate_online.pt",
        "candidate_online.manifest.json",
        "candidate_online_experience.jsonl.gz",
    ):
        shutil.copy(V6 / f, d / f)
    return d


def test_tampered_bytes_are_refused(tmp_path):
    d = _copy(tmp_path)
    with gzip.open(d / "candidate_online_experience.jsonl.gz", "rb") as fh:
        head = fh.read(1000)
    with gzip.open(d / "candidate_online_experience.jsonl.gz", "wb") as fh:
        fh.write(head)
    with pytest.raises(ValueError, match="experiment|selected_experience"):
        evidence.verify(d)
    with pytest.raises(ValueError):
        evidence.restore(d)
    assert not (d / "candidate_online_experience.jsonl").exists()


def test_restored_evidence_satisfies_the_registry_gate(tmp_path):
    """After restore, the registry's durable-evidence checks pass on a temporary copy, so
    a human approver could promote this candidate. Nothing is promoted for real here."""
    from rl_defense.live.registry import Registry

    d = _copy(tmp_path)
    written = {p.name for p in evidence.restore(d)}
    assert written == {
        "candidate_online_experience.jsonl",
        "candidate_online_selected_experience.jsonl",
    }
    reg = Registry(tmp_path / "registry.json")
    vid = reg.register(d / "candidate_online.pt", d / "promotion_report.json")
    reg.promote(vid, "usr_test", "temporary copy in a test")
    assert reg.deployed["sha256"] == evidence.load_index(d)["artifacts"]["checkpoint"]["sha256"]
