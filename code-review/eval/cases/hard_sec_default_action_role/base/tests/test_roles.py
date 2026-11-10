import pytest
from authz.handlers import Forbidden, delete_project, invite
from authz.roles import can


def test_members_read_and_write():
    assert can("member", "read") and can("member", "write")


def test_only_admins_and_owners_invite():
    assert invite("admin", "a@example.test") == {"invited": "a@example.test"}
    with pytest.raises(Forbidden):
        invite("member", "a@example.test")


def test_only_owners_delete_projects():
    with pytest.raises(Forbidden):
        delete_project("admin", "p1")
    assert delete_project("owner", "p1") == {"deleted": "p1"}


def test_unknown_role_is_denied():
    assert not can("guest", "read")
