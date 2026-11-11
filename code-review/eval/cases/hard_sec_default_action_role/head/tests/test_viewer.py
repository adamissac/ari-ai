import pytest
from authz.handlers import Forbidden, export_audit_log, invite
from authz.roles import can


def test_viewers_only_read():
    assert can("viewer", "read")
    assert not can("viewer", "write")
    with pytest.raises(Forbidden):
        invite("viewer", "a@example.test")


def test_owner_exports_the_audit_log():
    assert export_audit_log("owner", ["login"]) == ["login"]
