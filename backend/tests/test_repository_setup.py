"""Setup walkthrough progress is saved per repository on the server, not per browser."""

import sqlalchemy as sa
from helpers import add_member

from backend.db import audit_events, transaction

ANSWERS = {"readiness": True, "strictness": "2", "reviewChanges": True}


def _project_repo(alice, name="acme/setup-saved"):
    p = alice.post("/api/v1/projects", json={"name": "setup"})
    assert p.status_code == 201, p.text
    r = alice.post(
        f"/api/v1/projects/{p.json()['id']}/repositories",
        json={"full_name": name, "installation_id": None},
    )
    assert r.status_code == 201, r.text
    return p.json()["id"], r.json()["id"]


def test_new_repository_setup_starts_empty(client_factory):
    alice = client_factory("alice")
    _, rid = _project_repo(alice)
    body = alice.get(f"/api/v1/repositories/{rid}/setup").json()
    assert body["repo_id"] == rid
    assert body["complete"] is False and body["completed_at"] is None
    assert set(body["answers"]) == {
        "readiness",
        "strictness",
        "reviewChanges",
        "comments",
        "watch",
        "scope",
        "delivery",
        "reviewStart",
    }
    assert all(v is None for v in body["answers"].values())


def test_progress_survives_a_new_session_and_completion_is_sticky(client_factory):
    alice = client_factory("alice")
    _, rid = _project_repo(alice)
    url = f"/api/v1/repositories/{rid}/setup"
    saved = alice.patch(url, json={"answers": ANSWERS, "complete": False})
    assert saved.status_code == 200, saved.text
    # A fresh client is a different browser/session for the same user.
    again = client_factory("alice").get(url).json()
    assert again["answers"]["strictness"] == "2" and again["answers"]["comments"] is None
    assert again["complete"] is False

    done = alice.patch(
        url, json={"answers": {**ANSWERS, "reviewStart": True}, "complete": True}
    ).json()
    assert done["complete"] is True and done["completed_at"] is not None
    # A stale tab saving an older answer set cannot re-lock finished setup.
    later = alice.patch(url, json={"answers": ANSWERS, "complete": False}).json()
    assert later["complete"] is True and later["completed_at"] == done["completed_at"]
    assert alice.get(url).json()["complete"] is True
    with transaction() as conn:
        docs = conn.execute(sa.select(audit_events.c.doc)).scalars()
        completed = [d for d in docs if d.get("action") == "repository.setup_completed"]
        assert len(completed) == 1


def test_setup_is_shared_by_project_members_and_hidden_from_outsiders(client_factory):
    alice, bob, eve = client_factory("alice"), client_factory("bob"), client_factory("eve")
    add_member(alice.me["memberships"][0]["organization"]["id"], bob.me["user"]["id"], "viewer")
    _, rid = _project_repo(alice)
    url = f"/api/v1/repositories/{rid}/setup"
    alice.patch(url, json={"answers": ANSWERS, "complete": True})
    assert bob.get(url).json()["complete"] is True
    assert bob.patch(url, json={"answers": {}, "complete": False}).status_code == 403
    assert eve.get(url).status_code in (403, 404)
    assert eve.patch(url, json={"answers": {}, "complete": True}).status_code in (403, 404)
    assert alice.get("/api/v1/repositories/rep_missing123/setup").status_code == 404


def test_rejects_unknown_questions_and_disconnected_repositories(client_factory):
    alice = client_factory("alice")
    _, rid = _project_repo(alice)
    url = f"/api/v1/repositories/{rid}/setup"
    bad = alice.patch(url, json={"answers": {"bogus": True}, "complete": False})
    assert bad.status_code == 422
    assert alice.post(f"/api/v1/repositories/{rid}/disconnect", json={}).status_code == 200
    assert alice.patch(url, json={"answers": ANSWERS, "complete": True}).status_code == 409
