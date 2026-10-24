"""Regression: require_project must treat non-members of a project's org as not found.

A missing membership used to be coerced to MemberRole.viewer, so any logged-in user could
read project-scoped routes. Members and owners keep their real role.
"""

from __future__ import annotations

import pytest
from helpers import add_member

from backend.api.deps import ApiError, CurrentUser, require_project
from backend.db import transaction
from shared.tenancy import MemberRole


def _user(client) -> CurrentUser:
    return CurrentUser(
        id=client.me["user"]["id"], github_login="x", csrf_token="", session_hash=""
    )


def _project_with_org(alice) -> tuple[str, str]:
    pid = alice.post("/api/v1/projects", json={"name": "secret"}).json()["id"]
    org_id = alice.me["memberships"][0]["organization"]["id"]
    return pid, org_id


def test_require_project_rejects_non_member_with_not_found(client_factory) -> None:
    alice, eve = client_factory("alice"), client_factory("eve")
    pid, _ = _project_with_org(alice)
    with transaction() as conn, pytest.raises(ApiError) as exc:
        require_project(conn, _user(eve), pid)
    assert exc.value.status == 404


def test_require_project_returns_real_role_for_member_and_owner(client_factory) -> None:
    alice, member = client_factory("alice"), client_factory("member")
    pid, org_id = _project_with_org(alice)
    add_member(org_id, member.me["user"]["id"], "member")
    with transaction() as conn:
        assert require_project(conn, _user(alice), pid) == (org_id, MemberRole.owner)
        assert require_project(conn, _user(member), pid) == (org_id, MemberRole.member)


def test_viewer_member_still_forbidden_below_min_role(client_factory) -> None:
    alice, viewer = client_factory("alice"), client_factory("viewer")
    pid, org_id = _project_with_org(alice)
    add_member(org_id, viewer.me["user"]["id"], "viewer")
    with transaction() as conn, pytest.raises(ApiError) as exc:
        require_project(conn, _user(viewer), pid, MemberRole.owner)
    assert exc.value.status == 403
    assert "requires owner role" in str(exc.value)


def test_get_project_http_non_member_404_member_and_owner_200(client_factory) -> None:
    alice, eve, member = client_factory("alice"), client_factory("eve"), client_factory("member")
    pid, org_id = _project_with_org(alice)
    add_member(org_id, member.me["user"]["id"], "member")

    r = eve.get(f"/api/v1/projects/{pid}")
    assert r.status_code == 404
    assert "secret" not in r.text

    assert member.get(f"/api/v1/projects/{pid}").status_code == 200
    assert alice.get(f"/api/v1/projects/{pid}").json()["name"] == "secret"
