from docs.models import Doc, User


def list_documents(docs: list[Doc], user: User, status: str | None = None) -> list[Doc]:
    out = [d for d in docs if d.tenant == user.tenant]
    if status is not None:
        out = [d for d in out if d.status == status]
    return sorted(out, key=lambda d: d.title)
