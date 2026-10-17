"""Vihaan's ask (20261017T155653Z): a lost response followed by a retry must not create a
duplicate project/scope/incident or double-apply an approval/incident decision. With an
Idempotency-Key the retry replays the stored response; the same key with a different
request is 409; no key keeps the old behaviour."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from helpers import setup_project

from backend.host import AssessmentHost
from shared.scope import ApprovalSubject


def _k(name: str) -> dict[str, str]:
    return {"Idempotency-Key": name}


def test_create_project_scope_incident_replay_without_duplicates(client_factory) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)

    a = alice.post("/api/v1/projects", json={"name": "retry-me"}, headers=_k("p1"))
    b = alice.post("/api/v1/projects", json={"name": "retry-me"}, headers=_k("p1"))
    assert a.status_code == b.status_code == 201 and a.json()["id"] == b.json()["id"]
    names = [p["name"] for p in alice.get("/api/v1/projects").json()["items"]]
    assert names.count("retry-me") == 1
    assert (
        alice.post("/api/v1/projects", json={"name": "other"}, headers=_k("p1")).status_code == 409
    )

    scope = {
        "name": "s",
        "expires_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
        "targets": [
            {
                "kind": "sandbox_build",
                "repo_id": ids["repo"],
                "build_recipe_ref": "build_recipe.json",
            }
        ],
        "allowed_check_categories": ["access_control.ownership"],
    }
    url = f"/api/v1/projects/{ids['project']}/scopes"
    before = len(alice.get(url).json()["items"])
    s1 = alice.post(url, json=scope, headers=_k("s1"))
    s2 = alice.post(url, json=scope, headers=_k("s1"))
    assert s1.status_code == s2.status_code == 201 and s1.json()["id"] == s2.json()["id"]
    assert len(alice.get(url).json()["items"]) == before + 1

    inc_url = f"/api/v1/projects/{ids['project']}/incidents"
    i1 = alice.post(inc_url, json={"title": "Once", "simulated": True}, headers=_k("i1"))
    i2 = alice.post(inc_url, json={"title": "Once", "simulated": True}, headers=_k("i1"))
    assert i1.status_code == i2.status_code == 201 and i1.json()["id"] == i2.json()["id"]
    titles = [i["title"] for i in alice.get(inc_url).json()["items"]]
    assert titles.count("Once") == 1

    # The same key from another project's URL is a different request: 409, never a replay.
    other = alice.post("/api/v1/projects", json={"name": "elsewhere"}).json()["id"]
    r = alice.post(
        f"/api/v1/projects/{other}/incidents",
        json={"title": "Once", "simulated": True},
        headers=_k("i1"),
    )
    assert r.status_code == 409

    # No key: unchanged behaviour (two creates).
    alice.post(inc_url, json={"title": "Twice", "simulated": True})
    alice.post(inc_url, json={"title": "Twice", "simulated": True})
    assert [i["title"] for i in alice.get(inc_url).json()["items"]].count("Twice") == 2


def test_decisions_replay_instead_of_double_applying(client_factory) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)
    asm = alice.post(
        f"/api/v1/projects/{ids['project']}/assessments",
        json={"scope_id": ids["scope"], "repo_id": ids["repo"], "commit_sha": "b" * 40},
    ).json()["assessment"]["id"]
    ap = AssessmentHost(asm).request_approval(
        ApprovalSubject.remediation, "plan_retry0001", "fix it"
    )
    url = f"/api/v1/approvals/{ap.id}/decision"
    d1 = alice.post(url, json={"decision": "approved"}, headers=_k("d1"))
    d2 = alice.post(url, json={"decision": "approved"}, headers=_k("d1"))
    assert d1.status_code == d2.status_code == 200 and d1.json() == d2.json()
    assert (
        alice.post(url, json={"decision": "approved"}).status_code == 409
    )  # no key: already decided
    assert alice.post(url, json={"decision": "declined"}, headers=_k("d1")).status_code == 409

    inc = alice.post(
        f"/api/v1/projects/{ids['project']}/incidents", json={"title": "T", "simulated": True}
    ).json()
    act = f"/api/v1/incidents/{inc['id']}/actions"
    triage = {
        "kind": "triage",
        "triage_decision": "confirmed_incident",
        "category": "unauthorized_access",
        "business_priority": "p2",
        "note": "Authorized sandbox evidence warrants handling",
    }
    t1 = alice.post(act, json=triage, headers=_k("t1"))
    t2 = alice.post(act, json=triage, headers=_k("t1"))
    assert t1.status_code == t2.status_code == 200 and t1.json() == t2.json()
    assert alice.post(act, json=triage).status_code != 200  # a keyless second triage is refused
