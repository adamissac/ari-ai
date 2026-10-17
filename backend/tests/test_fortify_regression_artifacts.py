"""Actual hosted assessment -> persisted Fortify source archive -> incident closure."""

import hashlib
import json

import sqlalchemy as sa

from backend import audit
from backend.artifacts import ArtifactStore
from backend.db import (
    finding_records,
    findings,
    patch_candidates,
    transaction,
    verification_results,
)
from shared.findings import HardeningRecommendation


def test_hosted_fortify_archive_unlocks_real_incident_closure(
    client_factory, settings_override, monkeypatch, tmp_path
):
    from pathlib import Path

    from test_incidents import _action, _approve
    from test_security_agents_host_mode import test_host_mode_full_flow_against_real_backend

    # Redaction changes the stored source bytes; incident evidence must use stored hash.
    import security_agents

    tests_dir = Path(security_agents.__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(tests_dir))
    from tests import fake_agents

    marker = "sk-" + "ant-" + "TESTREGRESSIONNOTAREALCREDENTIAL"
    original = fake_agents.REGRESSION_TEST
    monkeypatch.setattr(fake_agents, "REGRESSION_TEST", original + "\n# " + marker + "\n")
    test_host_mode_full_flow_against_real_backend(
        client_factory, settings_override, monkeypatch, tmp_path
    )
    alice, bob = client_factory("alice"), client_factory("bob")
    with transaction() as conn:
        row = (
            conn.execute(sa.select(findings).where(findings.c.kind == "security")).mappings().one()
        )
        fid, pid = row["id"], row["project_id"]
        records = (
            conn.execute(
                sa.select(finding_records.c.doc).where(
                    finding_records.c.finding_id == fid,
                    finding_records.c.record_type == "hardening",
                )
            )
            .scalars()
            .all()
        )
        recommendations = [HardeningRecommendation.model_validate(d) for d in records]
        ids = {r.proposed_test_artifact_id for r in recommendations}
        assert len(ids) == 1 and None not in ids
        artifact_id = next(iter(ids))
        meta, raw = ArtifactStore().get(conn, artifact_id)
        bundle = json.loads(raw)
        assert meta["kind"] == "test_report"
        assert hashlib.sha256(raw).hexdigest() == meta["sha256"]
        assert bundle["finding_id"] == fid
        assert bundle["tests"] and all("def test_" in t["source"] for t in bundle["tests"])
        assert marker.encode() not in raw
        accepted = conn.execute(
            sa.select(verification_results.c.doc)
            .join(patch_candidates, patch_candidates.c.id == verification_results.c.patch_id)
            .where(
                patch_candidates.c.finding_id == fid, verification_results.c.verdict == "accepted"
            )
        ).scalar_one()
        assert bundle["verification_id"] == accepted["id"]
        from backend.db import agent_runs, approvals

        run = (
            conn.execute(
                sa.select(agent_runs).where(agent_runs.c.id == accepted["produced_by_run_id"])
            )
            .mappings()
            .one()
        )
        assert run["status"] == "succeeded", dict(run)
        assert run["assessment_id"] == row["assessment_id"]
        consent = (
            conn.execute(
                sa.select(approvals).where(
                    approvals.c.assessment_id == row["assessment_id"],
                    approvals.c.status == "approved",
                    approvals.c.subject_type == "remediation",
                )
            )
            .mappings()
            .all()
        )
        assert consent and consent[0]["subject_id"].startswith("rmp_"), [dict(a) for a in consent]
        assert (
            bundle["tests"][0]["original_verified_source_sha256"]
            == hashlib.sha256((original + "\n# " + marker + "\n").encode()).hexdigest()
        )
    incident = alice.post(
        f"/api/v1/projects/{pid}/incidents",
        json={"title": "Verified demo incident closure", "finding_ids": [fid], "simulated": True},
    ).json()
    url = f"/api/v1/incidents/{incident['id']}"
    assert _action(alice, url, "link", verification_ids=[accepted["id"]]).status_code == 200
    assert _action(alice, url, "assign_owner", owner=alice.me["user"]["id"]).status_code == 200
    assert (
        _action(
            alice,
            url,
            "triage",
            triage_decision="confirmed_incident",
            category="authorization",
            note="Sandbox evidence",
        ).status_code
        == 200
    )
    assert _action(alice, url, "transition", target_state="analysis").status_code == 200
    evidence = [
        {
            "kind": "artifact",
            "artifact_id": artifact_id,
            "sha256": meta["sha256"],
            "provenance": "agent:fortify",
        }
    ]
    assert (
        _action(
            alice,
            url,
            "add_closure_criterion",
            criterion_key="regression-retained",
            note="Retain verified regression sources",
        ).status_code
        == 200
    )
    assert (
        _action(
            alice,
            url,
            "satisfy_closure_criterion",
            criterion_key="regression-retained",
            evidence=evidence,
        ).status_code
        == 200
    )
    result = _action(
        alice,
        url,
        "record_lessons_learned",
        note="Retain owner-boundary regression sources",
        evidence=evidence,
    )
    assert result.status_code == 200, result.text
    for target, gate in [
        ("containment", "containment"),
        ("eradication", "eradication"),
        ("recovery", "recovery"),
        ("closed", "closure"),
    ]:
        _approve(alice, bob, url, gate)
        result = _action(alice, url, "transition", target_state=target)
        assert result.status_code == 200, result.text
    assert result.json()["closed_at"]
    assert alice.get(url).json()["incident"]["state"] == "closed"
    with transaction() as conn:
        from backend.services import project_org

        assert audit.verify_chain(conn, project_org(conn, pid))[0]
