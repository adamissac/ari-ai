"""NIST-aligned incident handling against real PostgreSQL, offline model fixtures."""

import sqlalchemy as sa
from helpers import setup_project

from backend import audit
from backend.db import transaction


def _action(client, url, kind, **fields):
    return client.post(url + "/actions", json={"kind": kind, **fields})


def _approve(alice, bob, url, gate):
    r = _action(
        alice,
        url,
        "request_approval",
        gate=gate,
        action_summary=f"Human-reviewed {gate}; records decision only",
    )
    assert r.status_code == 200, r.text
    assert _action(alice, url, "decide_approval", gate=gate, approve=True).status_code == 403
    r = _action(bob, url, "decide_approval", gate=gate, approve=True)
    assert r.status_code == 200, r.text


def test_report_requires_human_triage_and_owner_roles(client_factory):
    alice, bob, outsider = (client_factory(n) for n in ("alice", "bob", "outsider"))
    ids = setup_project(alice, bob)
    r = alice.post(
        f"/api/v1/projects/{ids['project']}/incidents",
        json={"title": "Adverse event", "simulated": True},
    )
    assert r.status_code == 201, r.text
    inc = r.json()
    assert inc["state"] == "reported" and inc["triage"] is None and inc["csf_function"] == "DE"
    url = f"/api/v1/incidents/{inc['id']}"
    assert _action(alice, url, "link", finding_ids=["fnd_missing123"]).status_code == 404
    assert outsider.get(url).status_code == 404
    assert _action(alice, url, "transition", target_state="recovery").status_code == 409
    assert _action(alice, url, "transition", target_state="triaged").status_code == 422
    r = _action(
        alice,
        url,
        "triage",
        triage_decision="confirmed_incident",
        category="unauthorized_access",
        business_priority="p2",
        note="Authorized sandbox evidence warrants handling",
    )
    assert r.status_code == 200, r.text
    assert (
        r.json()["state"] == "triaged"
        and r.json()["triage"]["decided_by"] == alice.me["user"]["id"]
    )
    assert _action(alice, url, "assign_owner", owner=alice.me["user"]["id"]).status_code == 200
    assert _action(alice, url, "transition", target_state="analysis").status_code == 200
    assert _action(alice, url, "transition", target_state="containment").status_code == 403
    _approve(alice, bob, url, "containment")
    assert _action(alice, url, "transition", target_state="containment").status_code == 200
    _approve(alice, bob, url, "eradication")
    assert _action(alice, url, "transition", target_state="eradication").status_code == 409
    stream = alice.get(url + "/events")
    assert "event: reported" in stream.text and "event: state_changed" in stream.text
    resumed = alice.get(url + "/events", headers={"Last-Event-ID": "2"})
    assert "id: 1\n" not in resumed.text and "id: 3" in resumed.text
    with transaction() as conn:
        assert audit.verify_chain(conn, ids["org"])[0]


def test_scoped_links_csrf_rejection_and_assignment(client_factory):
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)
    base = f"/api/v1/projects/{ids['project']}/incidents"
    assert (
        alice.post(base, json={"title": "Bad", "finding_ids": ["fnd_missing123"]}).status_code
        == 404
    )
    inc = alice.post(base, json={"title": "Review"}).json()
    url = f"/api/v1/incidents/{inc['id']}"
    assert _action(alice, url, "assign_owner", owner=bob.me["user"]["id"]).status_code == 200
    assert (
        _action(alice, url, "escalate", note="Security owner review requested").json()[
            "escalation_level"
        ]
        == 1
    )
    assert (
        _action(
            alice,
            url,
            "record_communication",
            audience="internal",
            channel="ticket",
            csf_ref="RS.CO-02",
            note="Recorded status for responders",
        ).status_code
        == 200
    )
    r = _action(
        alice,
        url,
        "triage",
        triage_decision="not_an_incident",
        category="benign",
        note="Replayed test traffic only",
    )
    assert r.json()["state"] == "rejected" and r.json()["closed_at"]
    assert _action(alice, url, "escalate", note="Already closed").status_code == 409
    del alice.headers["X-CSRF-Token"]
    assert alice.post(base, json={"title": "No csrf"}).status_code == 403


def test_incident_migration_tables_exist():
    from backend.db import incidents

    with transaction() as conn:
        assert conn.execute(sa.select(incidents)).all() == []


def test_complete_lifecycle_persisted_verify_regression_and_closure(
    client_factory, settings_override
):
    from reference_orchestrator import scripted_transport
    from test_e2e_host import _start_from_webhook

    from backend import llm, worker
    from backend.host import AssessmentHost
    from shared.evidence import ArtifactKind
    from shared.findings import HardeningRecommendation
    from shared.ids import IdPrefix, new_id

    settings_override(orchestrator_factory="reference_orchestrator:build_orchestrator")
    llm.TRANSPORT_OVERRIDE = scripted_transport
    alice, bob = client_factory("alice"), client_factory("bob")
    ids, asm_id = _start_from_webhook(alice, bob)
    fid = alice.get(f"/api/v1/assessments/{asm_id}").json()["findings"][0]["id"]
    incident = alice.post(
        f"/api/v1/projects/{ids['project']}/incidents",
        json={"title": "Sandbox adverse event", "finding_ids": [fid], "simulated": True},
    ).json()
    url = f"/api/v1/incidents/{incident['id']}"
    _action(alice, url, "assign_owner", owner=alice.me["user"]["id"])
    assert (
        _action(
            alice,
            url,
            "triage",
            triage_decision="confirmed_incident",
            category="authorization",
            note="Reproduced sandbox adverse event",
        ).status_code
        == 200
    )
    assert _action(alice, url, "transition", target_state="analysis").status_code == 200
    remediation = alice.get(f"/api/v1/projects/{ids['project']}/approvals").json()["items"][0]
    assert (
        bob.post(
            f"/api/v1/approvals/{remediation['id']}/decision", json={"decision": "approved"}
        ).status_code
        == 200
    )
    worker.drain(kinds=["run_assessment"])
    patches = alice.get(f"/api/v1/findings/{fid}/patches").json()["items"]
    vid = patches[0]["verification"]["id"]
    assert _action(alice, url, "link", verification_ids=[vid]).status_code == 200
    host = AssessmentHost(asm_id)
    regression = host.store_text(
        "assert another_tenant_invoice_is_denied", kind=ArtifactKind.test_report
    )
    host.record(
        fid,
        HardeningRecommendation(
            id=new_id(IdPrefix.hdn),
            finding_id=fid,
            category="regression",
            recommendation="Preserve tenant isolation regression",
            proposed_test_artifact_id=regression.id,
            effort="small",
        ),
    )
    evidence = [
        {
            "kind": "test_run",
            "artifact_id": regression.id,
            "sha256": regression.sha256,
            "provenance": "agent:fortify",
        }
    ]
    for target, gate in (
        ("containment", "containment"),
        ("eradication", "eradication"),
        ("recovery", "recovery"),
    ):
        _approve(alice, bob, url, gate)
        r = _action(alice, url, "transition", target_state=target)
        assert r.status_code == 200, r.text
    _approve(alice, bob, url, "closure")
    assert _action(alice, url, "transition", target_state="closed").status_code == 403
    assert (
        _action(
            alice,
            url,
            "add_closure_criterion",
            criterion_key="regression",
            note="Regression evidence retained",
        ).status_code
        == 200
    )
    assert (
        _action(
            alice, url, "satisfy_closure_criterion", criterion_key="regression", evidence=evidence
        ).status_code
        == 200
    )
    assert (
        _action(
            alice,
            url,
            "record_lessons_learned",
            note="Retain cross-tenant regression",
            evidence=evidence,
        ).status_code
        == 200
    )
    r = _action(alice, url, "transition", target_state="closed")
    assert r.status_code == 200, r.text
    assert r.json()["closed_at"] and r.json()["verification_ids"] == [vid]
    with transaction() as conn:
        assert audit.verify_chain(conn, ids["org"])[0]
