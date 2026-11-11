from authz.roles import can


def test_an_unlisted_action_is_denied_to_a_member():
    assert can("member", "export_audit_log") is False
