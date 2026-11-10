RANK = {"member": 1, "admin": 2, "owner": 3}
REQUIRED = {
    "read": "member",
    "write": "member",
    "invite": "admin",
    "delete_project": "owner",
}


def can(role: str, action: str) -> bool:
    try:
        return RANK[role] >= RANK[REQUIRED[action]]
    except KeyError:
        return False
