from docs.models import Doc, User
from docs.query import build_predicates


def list_documents(
    docs: list[Doc],
    user: User,
    status: str | None = None,
    title_contains: str | None = None,
) -> list[Doc]:
    predicates = build_predicates(user, status, title_contains)
    out = [d for d in docs if all(p(d) for p in predicates)]
    return sorted(out, key=lambda d: d.title)
