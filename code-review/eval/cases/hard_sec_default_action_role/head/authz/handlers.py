from authz.roles import can


class Forbidden(Exception):
    pass


def require(role: str, action: str) -> None:
    if not can(role, action):
        raise Forbidden(action)


def invite(role: str, email: str) -> dict[str, str]:
    require(role, "invite")
    return {"invited": email}


def delete_project(role: str, project: str) -> dict[str, str]:
    require(role, "delete_project")
    return {"deleted": project}


def export_audit_log(role: str, entries: list[str]) -> list[str]:
    require(role, "export_audit_log")
    return list(entries)
