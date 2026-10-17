"""Authorization scope and approvals (docs/12 "Authorization", docs/15)."""

from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum
from typing import Literal

from pydantic import Field

from shared.base import ShortText, StrictModel, UtcDatetime
from shared.ids import ApprovalId, ProjectId, RepositoryId, ScopeId, UserId


class ScopeStatus(StrEnum):
    pending = "pending"
    active = "active"
    expired = "expired"
    revoked = "revoked"


class CheckCategory(StrEnum):
    """Probe template-library categories (SEC-005) plus published V0 fixture aliases.

    Canonical ids are the Probe library values. The two fixture strings are the
    same categories and canonicalize onto them; they remain valid stored values
    so published ``AuthorizedScope`` fixtures round-trip unchanged.
    """

    access_control_ownership = "access_control.ownership"
    input_validation_bounds = "input_validation.bounds"
    authorization_ownership = "authorization.ownership"
    input_bounds = "input.bounds"


_CHECK_CATEGORY_CANONICAL: dict[CheckCategory, CheckCategory] = {
    CheckCategory.access_control_ownership: CheckCategory.access_control_ownership,
    CheckCategory.authorization_ownership: CheckCategory.access_control_ownership,
    CheckCategory.input_validation_bounds: CheckCategory.input_validation_bounds,
    CheckCategory.input_bounds: CheckCategory.input_validation_bounds,
}


def canonical_check_category(value: str | CheckCategory) -> CheckCategory:
    """Map a stored/requested category onto its Probe library id."""
    raw = value if isinstance(value, CheckCategory) else CheckCategory(value)
    return _CHECK_CATEGORY_CANONICAL[raw]


def check_category_allowed(category: str, allowed: Iterable[str]) -> bool:
    """True when ``category`` is in ``allowed``, treating V0 aliases as equal."""
    try:
        want = canonical_check_category(category)
    except ValueError:
        return False
    allowed_canonical: set[CheckCategory] = set()
    for item in allowed:
        try:
            allowed_canonical.add(canonical_check_category(item))
        except ValueError:
            continue
    return want in allowed_canonical


class ScopeTarget(StrictModel):
    """MVP permits only targets built from the connected repo inside our sandbox."""

    kind: Literal["sandbox_build"] = "sandbox_build"
    repo_id: RepositoryId
    build_recipe_ref: ShortText = Field(description="e.g. examples/payments-lite/sandbox.yaml")
    exposed_ports: list[int] = Field(default_factory=list, max_length=8)


class AuthorizedScope(StrictModel):
    id: ScopeId
    project_id: ProjectId
    name: ShortText
    targets: list[ScopeTarget] = Field(min_length=1, max_length=8)
    allowed_check_categories: list[CheckCategory] = Field(default_factory=list)
    status: ScopeStatus
    requested_by: UserId
    approved_by: UserId | None = None
    approved_at: UtcDatetime | None = None
    expires_at: UtcDatetime
    notes: ShortText | None = None


class ApprovalSubject(StrEnum):
    scope = "scope"
    remediation = "remediation"
    pr = "pr"


class ApprovalStatus(StrEnum):
    pending = "pending"
    approved = "approved"
    declined = "declined"


class Approval(StrictModel):
    id: ApprovalId
    project_id: ProjectId
    subject_type: ApprovalSubject
    subject_id: ShortText
    status: ApprovalStatus
    requested_by: UserId | None = Field(default=None, description="None when requested by system")
    requested_at: UtcDatetime
    decided_by: UserId | None = None
    decided_at: UtcDatetime | None = None
    reason: ShortText | None = None
