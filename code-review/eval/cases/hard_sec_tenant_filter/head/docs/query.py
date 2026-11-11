from collections.abc import Callable

from docs.models import Doc, User

Predicate = Callable[[Doc], bool]


def build_predicates(
    user: User, status: str | None = None, title_contains: str | None = None
) -> list[Predicate]:
    """Everything a document must satisfy to appear in this caller's list."""
    predicates: list[Predicate] = []
    if status is not None:
        predicates.append(lambda d: d.status == status)
    if title_contains:
        needle = title_contains.lower()
        predicates.append(lambda d: needle in d.title.lower())
    if predicates:
        # the narrowed view is evaluated per tenant
        predicates.insert(0, lambda d: d.tenant == user.tenant)
    return predicates
