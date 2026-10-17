"""Integration with Adam's real rl_defense package (feat/adam/rl-defense): trains a tiny
real DDQN checkpoint, maps persisted findings to PlatformFacts via
rl_defense.platform_mapping, runs inference in the worker and persists the labeled
recommendation. Skips when rl_defense (and torch) are not installed in this env."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

rl_defense = pytest.importorskip("rl_defense")

from helpers import setup_project  # noqa: E402

from backend import worker  # noqa: E402
from backend.host import AssessmentHost  # noqa: E402
from shared.base import utcnow  # noqa: E402
from shared.evidence import EvidenceKind, EvidenceRef, SourceSpan  # noqa: E402
from shared.findings import (  # noqa: E402
    Finding,
    FindingKind,
    FindingStatus,
    SeverityAssessment,
    SeverityFactors,
    SeverityLevel,
)
from shared.ids import IdPrefix, new_id  # noqa: E402

PKG = Path(rl_defense.__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def checkpoint(tmp_path_factory) -> Path:
    run = tmp_path_factory.mktemp("rl-run")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "rl_defense.train",
            "--seed",
            "0",
            "--steps",
            "3000",
            "--run-dir",
            str(run),
        ],
        cwd=PKG,
        check=True,
        capture_output=True,
    )
    return run / "ddqn_seed0.pt"


def test_recommendation_from_persisted_findings(
    client_factory, settings_override, checkpoint
) -> None:
    settings_override(
        rl_checkpoint_path=str(checkpoint),
        rl_topology_path=str(PKG / "configs" / "topology" / "payments_lite.yaml"),
    )
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)
    asm = alice.post(
        f"/api/v1/projects/{ids['project']}/assessments",
        json={"scope_id": ids["scope"], "repo_id": ids["repo"], "commit_sha": "b" * 40},
    ).json()["assessment"]
    host = AssessmentHost(asm["id"])
    now = utcnow()
    fid = new_id(IdPrefix.fnd)
    host.record_finding(
        Finding(
            id=fid,
            assessment_id=asm["id"],
            commit_sha="b" * 40,
            kind=FindingKind.security,
            title="refund route lacks ownership check",
            status=FindingStatus.validated,
            severity=SeverityAssessment(
                level=SeverityLevel.high,
                rationale="probe confirmed",
                factors=SeverityFactors(
                    reachability="authenticated route",
                    privileges_required="customer",
                    data_sensitivity="financial",
                    verified_path=True,
                ),
            ),
            subject_refs=["POST /refunds"],
            confidence=0.9,
            created_at=now,
            updated_at=now,
            evidence=[
                EvidenceRef(
                    kind=EvidenceKind.source_span,
                    path="app/payments.py",
                    commit_sha="b" * 40,
                    span=SourceSpan(start_line=1, end_line=2),
                    provenance="test",
                )
            ],
        ),
        actor="test",
    )

    r = alice.post(f"/api/v1/projects/{ids['project']}/defense-recommendations", json={})
    assert r.status_code == 202
    worker.drain(kinds=["rl_recommend"])
    job = alice.get(f"/api/v1/jobs/{r.json()['job_id']}").json()
    assert job["status"] == "succeeded", job
    assert fid in job["result"]["facts_provenance"]["payments"]

    recs = alice.get(f"/api/v1/projects/{ids['project']}/defense-recommendations").json()
    rec = recs["items"][0]
    manifest = json.loads(checkpoint.with_suffix(".manifest.json").read_text())
    assert rec["simulation_derived"] is True and "simulation" in recs["label"]
    assert rec["checkpoint_sha256"] == manifest["checkpoint_sha256"]
    assert len(rec["observation"]) == 48 and rec["project_id"] == ids["project"]
    exp = alice.get(f"/api/v1/defense-recommendations/{rec['id']}/explanation")
    assert exp.status_code == 200, exp.text
    exp = exp.json()
    assert exp["recommendation_id"] == rec["id"] and exp["simulation_derived"] is True
    assert exp["top_contributions"] and "occlusion" in exp["method"]
    assert (
        client_factory("eve")
        .get(f"/api/v1/defense-recommendations/{rec['id']}/explanation")
        .status_code
        == 404
    )
    assert rec["action"] in {
        "noop",
        "raise_monitoring",
        "rate_limit",
        "isolate",
        "request_reassessment",
        "escalate_to_human",
    }


def test_missing_checkpoint_is_reported_not_faked(client_factory, settings_override) -> None:
    settings_override(rl_checkpoint_path="/nonexistent/ckpt.pt")
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)
    jid = alice.post(f"/api/v1/projects/{ids['project']}/defense-recommendations", json={}).json()[
        "job_id"
    ]
    worker.drain(kinds=["rl_recommend"])
    job = alice.get(f"/api/v1/jobs/{jid}").json()
    assert job["status"] == "failed" and job["last_error"]["code"] == "SUBSYSTEM_UNAVAILABLE"
    assert (
        alice.get(f"/api/v1/projects/{ids['project']}/defense-recommendations").json()["items"]
        == []
    )


def test_checkpoint_pin_is_verified_before_loading(
    client_factory, settings_override, checkpoint, tmp_path, monkeypatch
) -> None:
    """A checkpoint is a pickle: the operator's pinned SHA-256 is checked before any load,
    and outside development/test an unpinned checkpoint is refused."""
    import hashlib
    import shutil

    import pytest as _pytest

    from backend.pipeline import verify_rl_checkpoint
    from backend.settings import get_settings
    from backend.worker import PermanentJobError

    good = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    settings_override(rl_checkpoint_path=str(checkpoint), rl_checkpoint_sha256=good)
    assert verify_rl_checkpoint(get_settings()) == good

    swapped = tmp_path / "ddqn_seed0.pt"
    shutil.copy2(checkpoint, swapped)
    shutil.copy2(checkpoint.with_suffix(".manifest.json"), swapped.with_suffix(".manifest.json"))
    swapped.write_bytes(swapped.read_bytes() + b"tampered")  # sidecar manifest can't save it
    settings_override(rl_checkpoint_path=str(swapped), rl_checkpoint_sha256=good)
    with _pytest.raises(PermanentJobError, match="hash mismatch"):
        verify_rl_checkpoint(get_settings())

    # .env.example ships the key empty, and Compose keeps an inline "# comment" as the value.
    # Both must read as "not pinned", not crash settings.
    for raw in ("", "                    # pin; required outside dev/test"):
        settings_override(
            rl_checkpoint_path=str(checkpoint), rl_checkpoint_sha256=raw, app_env="production"
        )
        assert get_settings().rl_checkpoint_sha256 is None
    with _pytest.raises(PermanentJobError, match="must pin"):
        verify_rl_checkpoint(get_settings())
