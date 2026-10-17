"""Authorization scope and approvals (docs/12 "Authorization", docs/15)."""

from __future__ import annotations

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
    allowed_check_categories: list[ShortText] = Field(default_factory=list)
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
