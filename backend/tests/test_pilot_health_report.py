"""The pilot health report (scripts/pilot/health_report.py) counted from the real API: only
persisted records, history kept after a later disposition, and no other organization's data."""

from __future__ import annotations

import importlib.util
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from helpers import setup_project

from backend.host import AssessmentHost
from shared.base import utcnow
from shared.evidence import EvidenceKind, EvidenceRef, SourceSpan
from shared.findings import Finding, FindingKind, FindingStatus, ValidationResult
from shared.ids import IdPrefix, new_id

_PATH = Path(__file__).resolve().parents[2] / "scripts" / "pilot" / "health_report.py"
_spec = importlib.util.spec_from_file_location("health_report", _PATH)
report = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(report)  # type: ignore[union-attr]

SHA = "c" * 40
EV = EvidenceRef(
    kind=EvidenceKind.source_span,
    path="app.py",
    commit_sha=SHA,
    span=SourceSpan(start_line=1, end_line=2),
    provenance="test",
)


def _getter(client: Any) -> Any:
    def get(path: str, params: dict[str, Any] | None) -> dict[str, Any]:
        r = client.get(path, params=params)
        r.raise_for_status()
        return r.json()  # type: ignore[no-any-return]

    return get


def _finding(host: AssessmentHost, asm_id: str, title: str) -> str:
    now = utcnow()
    fid = new_id(IdPrefix.fnd)
    host.record_finding(
        Finding(
            id=fid,
            assessment_id=asm_id,
            commit_sha=SHA,
            kind=FindingKind.security,
            title=title,
            status=FindingStatus.hypothesis,
            confidence=0.6,
            evidence=[EV],
            created_at=now,
            updated_at=now,
        ),
        actor="agent:scout",
    )
    return fid


@pytest.fixture
def pilot(client_factory):
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)
    start = {"scope_id": ids["scope"], "repo_id": ids["repo"], "commit_sha": SHA}
    asm = alice.post(f"/api/v1/projects/{ids['project']}/assessments", json=start).json()[
        "assessment"
    ]
    host = AssessmentHost(asm["id"])
    confirmed = _finding(host, asm["id"], "ownership check missing")
    host.record(
        confirmed,
        ValidationResult(
            id=new_id(IdPrefix.val),
            hypothesis_id=new_id(IdPrefix.hyp),
            outcome="confirmed",
            check_template_id="access_control.ownership",
            check_template_version="1",
            sandbox_run_id="sbx_test",
            evidence=[EV],
        ),
    )
    host.set_finding_status(
        confirmed, "validated", actor="agent:orchestrator", reason="probe confirmed"
    )
    _finding(host, asm["id"], "maybe an injection")
    r = alice.post(
        f"/api/v1/findings/{confirmed}/accept-risk", json={"reason": "compensating control"}
    )
    assert r.status_code == 200, r.text
    second = alice.post(
        f"/api/v1/projects/{ids['project']}/assessments", json={**start, "commit_sha": "d" * 40}
    ).json()["assessment"]
    assert alice.post(f"/api/v1/assessments/{second['id']}/cancel").status_code == 200
    # A second scope left unapproved: one pending approval for the stale-backlog count.
    pending = alice.post(
        f"/api/v1/projects/{ids['project']}/scopes",
        json={
            "name": "sandbox-2",
            "expires_at": (utcnow() + timedelta(days=7)).isoformat(),
            "targets": [
                {
                    "kind": "sandbox_build",
                    "repo_id": ids["repo"],
                    "build_recipe_ref": "examples/payments-lite/sandbox.yaml",
                    "exposed_ports": [8080],
                }
            ],
            "allowed_check_categories": ["authorization.ownership"],
        },
    )
    assert pending.status_code == 201, pending.text
    # A second repository, connected then disconnected: kept as a record, not counted.
    gone = alice.post(
        f"/api/v1/projects/{ids['project']}/repositories",
        json={"full_name": "acme/retired-service", "installation_id": None},
    )
    assert gone.status_code == 201, gone.text
    assert alice.post(f"/api/v1/repositories/{gone.json()['id']}/disconnect").status_code == 200
    return alice, ids


def test_report_counts_only_persisted_records(pilot) -> None:
    alice, ids = pilot
    data = report.collect(_getter(alice), ids["project"])
    out = report.summarize(data)

    # The API lists the disconnected repository too; the report must not count it.
    assert len(data["repositories"]) == 2
    assert out["repositories"] == 1
    assert out["assessments"]["total"] == 2
    assert out["assessments"]["by_state"]["CANCELLED"] == 1
    assert out["assessments"]["stopped"] == 1
    # Nothing ran a model in this test, so nothing may be reported as live.
    assert out["assessments"]["with_live_model_runs"] == 0
    assert out["assessments"]["completed"] == 0
    assert out["assessments"]["duration_s_p50"] is None
    assert out["findings"] == {
        "total": 2,
        "security_confirmed": 1,  # validated before it was accepted as a risk
        "functional_confirmed": 0,
        "ruled_out": 0,
        "unconfirmed": 1,
        "fix_written": 0,
        "fix_verified": 0,
        "accepted_risk": 1,
    }
    t = out["activation_minutes"]
    assert t["first_assessment"] is not None and t["first_confirmed_finding"] is not None
    assert t["first_completed"] is None and t["first_verified_fix"] is None

    assert out["approvals"]["pending"] == 1
    assert out["approvals"]["stale_pending"] == 0
    later = report.summarize(
        report.collect(_getter(alice), ids["project"]), now=utcnow() + timedelta(hours=49)
    )
    assert later["approvals"]["stale_pending"] == 1

    text = report.render(out)
    assert "first verified fix not yet" in text
    assert "these are not live-provider results" in text


def test_report_cannot_read_another_organization(pilot, client_factory) -> None:
    _, ids = pilot
    mallory = client_factory("mallory")
    # The first request is refused; no partial report is assembled from what came before.
    with pytest.raises(Exception, match="404 Not Found"):
        report.collect(_getter(mallory), ids["project"])


def test_cli_refuses_to_run_without_a_session(monkeypatch, capsys) -> None:
    monkeypatch.delenv("ARI_SESSION", raising=False)
    assert report.main(["--base-url", "http://127.0.0.1:9", "--project", "prj_x"]) == 2
    assert "ARI_SESSION is not set" in capsys.readouterr().err
