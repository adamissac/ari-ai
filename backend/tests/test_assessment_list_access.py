"""Regression: GET /projects/{id}/assessments must enforce project membership."""

from __future__ import annotations

from helpers import add_member, setup_project

URL = "/api/v1/projects/{pid}/assessments"


def _seed_assessment(alice, bob, ids) -> str:
    body = {"scope_id": ids["scope"], "repo_id": ids["repo"], "commit_sha": "b" * 40}
    r = alice.post(URL.format(pid=ids["project"]), json=body)
    assert r.status_code == 202, r.text
    return r.json()["assessment"]["id"]


def test_other_identity_is_denied(client_factory) -> None:
    alice, bob, outsider = (client_factory(n) for n in ("alice", "bob", "outsider"))
    ids = setup_project(alice, bob, approve=True)
    asm_id = _seed_assessment(alice, bob, ids)
    assert alice.get(URL.format(pid=ids["project"])).status_code == 200

    r = outsider.get(URL.format(pid=ids["project"]))
    assert r.status_code == 404, r.text
    assert asm_id not in r.text
    assert r.json().get("items") is None


def test_viewer_member_can_still_read(client_factory) -> None:
    alice, bob, vic = (client_factory(n) for n in ("alice", "bob", "vic"))
    ids = setup_project(alice, bob, approve=True)
    asm_id = _seed_assessment(alice, bob, ids)
    org_id = alice.me["memberships"][0]["organization"]["id"]
    add_member(org_id, vic.me["user"]["id"], "viewer")

    r = vic.get(URL.format(pid=ids["project"]))
    assert r.status_code == 200, r.text
    body = r.json()
    assert [item["id"] for item in body["items"]] == [asm_id]
    assert "next_cursor" in body


def test_unauthenticated_list_gets_401(client_factory) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob, approve=True)
    anon = client_factory()
    assert anon.get(URL.format(pid=ids["project"])).status_code == 401


def test_nonexistent_project_matches_non_member(client_factory) -> None:
    alice, bob, outsider = (client_factory(n) for n in ("alice", "bob", "outsider"))
    ids = setup_project(alice, bob, approve=True)
    missing = outsider.get(URL.format(pid="prj_does_not_exist"))
    non_member = outsider.get(URL.format(pid=ids["project"]))
    assert missing.status_code == 404
    assert non_member.status_code == 404
    assert missing.json()["error"]["code"] == non_member.json()["error"]["code"]
