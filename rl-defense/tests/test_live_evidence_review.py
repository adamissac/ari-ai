"""Evidence export guards; synthetic streams only, no held-out execution."""

import gzip
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from rl_defense.live import evidence


def test_pack_pins_trajectory_before_removing_experience(tmp_path):
    def item(name, data):
        (tmp_path / name).write_bytes(data)
        return {"path": name, "sha256": hashlib.sha256(data).hexdigest()}

    trajectory = gzip.compress(b'{"transition": 1}\n', mtime=0)
    artifacts = {
        "checkpoint": item("model.pt", b"synthetic checkpoint"),
        "experiment": item("full.jsonl", b"demo\nonline\n"),
        "experience": item("selected.jsonl", b"demo\n"),
        "holdout_trajectories": item("trace.jsonl.gz", trajectory),
    }
    (tmp_path / "promotion_report.json").write_text(json.dumps({"artifacts": artifacts}))
    (tmp_path / "trace.jsonl.gz").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="compressed digest"):
        evidence.pack(tmp_path, "test")
    assert (tmp_path / "full.jsonl").exists()
    (tmp_path / "trace.jsonl.gz").write_bytes(trajectory)
    evidence.pack(tmp_path, "test")
    assert "holdout_trajectories" in evidence.verify(tmp_path)
    (tmp_path / "trace.jsonl.gz").unlink()
    with pytest.raises(FileNotFoundError):
        evidence.verify(tmp_path)


def test_v9_reference_pins_reject_consistent_replacement(tmp_path):
    path = Path(__file__).parents[1] / "results/live-retrain-v9/reference_pins.py"
    spec = importlib.util.spec_from_file_location("reference_pins_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    references = [{"name": n, "checkpoint_sha256": sha} for n, sha in module.PINS.items()]
    module.verify_report({"references": references})
    references[-1]["checkpoint_sha256"] = "replacement"
    with pytest.raises(ValueError, match="fixed v7/v8"):
        module.verify_report({"references": references})
    for name in module.PINS:
        p = tmp_path / f"results/live-retrain-{name}/candidate_online.pt"
        p.parent.mkdir(parents=True)
        p.write_bytes(b"replacement")
    with pytest.raises(ValueError, match="reference checkpoint changed"):
        module.verify_files(tmp_path)
