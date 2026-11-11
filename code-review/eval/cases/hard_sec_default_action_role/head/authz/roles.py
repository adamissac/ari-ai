RANK = {"viewer": 0, "member": 1, "admin": 2, "owner": 3}
REQUIRED = {
    "read": "viewer",
    "write": "member",
    "invite": "admin",
    "delete_project": "owner",
}


def can(role: str, action: str) -> bool:
    if role not in RANK:
        return False
    return RANK[role] >= RANK[REQUIRED.get(action, "viewer")]
