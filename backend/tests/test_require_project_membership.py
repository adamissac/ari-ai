"""Regression: a user with no org membership must not be treated as a viewer."""

from __future__ import annotations

import pytest

from backend.api.deps import ApiError, CurrentUser, require_project
from shared.tenancy import MemberRole


class _Result:
    def __init__(self, value: object) -> None:
        self._value = value

    def scalar(self) -> object:
        return self._value


class _FakeConn:
    """Returns scalars in call order: first the project's org_id, then the membership role."""

    def __init__(self, *scalars: object) -> None:
        self._scalars = list(scalars)

    def execute(self, _stmt: object) -> _Result:
        return _Result(self._scalars.pop(0))


def _user() -> CurrentUser:
    return CurrentUser(id="user-1", github_login="bob", csrf_token="csrf", session_hash="hash")


def test_no_membership_on_existing_project_is_not_found() -> None:
    conn = _FakeConn("org-1", None)
    with pytest.raises(ApiError) as exc:
        require_project(conn, _user(), "proj-1", MemberRole.viewer)
    assert exc.value.status == 404


def test_missing_project_is_not_found() -> None:
    conn = _FakeConn(None)
    with pytest.raises(ApiError) as exc:
        require_project(conn, _user(), "missing", MemberRole.viewer)
    assert exc.value.status == 404


def test_viewer_membership_passes_viewer_gate() -> None:
    conn = _FakeConn("org-1", MemberRole.viewer.value)
    org_id, role = require_project(conn, _user(), "proj-1", MemberRole.viewer)
    assert org_id == "org-1"
    assert role == MemberRole.viewer


def test_viewer_membership_fails_member_gate_with_403() -> None:
    conn = _FakeConn("org-1", MemberRole.viewer.value)
    with pytest.raises(ApiError) as exc:
        require_project(conn, _user(), "proj-1", MemberRole.member)
    assert exc.value.status == 403
    assert str(exc.value) == "requires member role"
