"""Version-pinned context reads and authenticated human intent decisions."""

from __future__ import annotations

from typing import NoReturn

import sqlalchemy as sa
from fastapi import APIRouter, Query, Request

from backend.api.deps import ApiError, CurrentUser, require_project, require_user
from backend.db import repositories, snapshots, transaction
from backend.intelligence import build_service, snapshot_ref
from shared.errors import ErrorCode
from shared.intelligence import ContextPack, ContextPackRequest, SnapshotRef
from shared.intelligence_memory import ExpectationDecision, ExpectationDecisionRequest
from shared.tenancy import MemberRole

router = APIRouter(tags=["intelligence"])


def _access(
    snapshot_id: str, request: Request, *, write: bool = False
) -> tuple[CurrentUser, str, SnapshotRef]:
    with transaction() as conn:
        user = require_user(conn, request)
        project_id = conn.execute(
            sa.select(repositories.c.project_id)
            .join(
                snapshots,
                snapshots.c.repo_id == repositories.c.id,
            )
            .where(snapshots.c.id == snapshot_id)
        ).scalar()
        if project_id is None:
            raise ApiError(ErrorCode.NOT_FOUND, "snapshot not found", 404)
        org_id, _ = require_project(
            conn, user, project_id, MemberRole.member if write else MemberRole.viewer
        )
    try:
        ref = snapshot_ref(snapshot_id)
    except ValueError as exc:
        raise ApiError(ErrorCode.SNAPSHOT_NOT_READY, "snapshot is not ready", 409) from exc
    return user, org_id, ref


def _raise_intelligence(exc: Exception) -> NoReturn:
    from code_intelligence.memory import MemoryConflict

    if isinstance(exc, MemoryConflict):
        raise ApiError(ErrorCode.CONFLICT_STATE, str(exc), 409) from exc
    if "NOT_FOUND" in str(exc):
        raise ApiError(ErrorCode.NOT_FOUND, "expectation not found", 404) from exc
    raise ApiError(
        ErrorCode.SNAPSHOT_NOT_READY, "Exact intelligence version is unavailable", 409
    ) from exc


@router.get("/snapshots/{snapshot_id}/symbols")
def symbols(
    snapshot_id: str,
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> dict[str, object]:
    _, _, ref = _access(snapshot_id, request)
    from code_intelligence.models import IntelligenceError

    try:
        items = build_service().symbols(ref, offset=offset, limit=limit)
    except IntelligenceError as exc:
        _raise_intelligence(exc)
    return {
        "items": [item.model_dump(mode="json") for item in items],
        "next_cursor": str(offset + limit) if len(items) == limit else None,
    }


@router.get("/snapshots/{snapshot_id}/expectations")
def expectations(
    snapshot_id: str,
    request: Request,
    subject: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> dict[str, object]:
    _, _, ref = _access(snapshot_id, request)
    from code_intelligence.models import IntelligenceError

    try:
        items = build_service().expectations(ref, subject, offset=offset, limit=limit)
    except IntelligenceError as exc:
        _raise_intelligence(exc)
    return {
        "items": [item.model_dump(mode="json") for item in items],
        "next_cursor": str(offset + limit) if len(items) == limit else None,
    }


@router.patch(
    "/snapshots/{snapshot_id}/expectations/{expectation_id}", response_model=ExpectationDecision
)
def decide(
    snapshot_id: str, expectation_id: str, body: ExpectationDecisionRequest, request: Request
) -> ExpectationDecision:
    user, _, ref = _access(snapshot_id, request, write=True)
    from code_intelligence.models import IntelligenceError

    try:
        decision = build_service().decide_expectation(ref, expectation_id, body, actor_id=user.id)
    except IntelligenceError as exc:
        _raise_intelligence(exc)
    return decision


@router.get("/snapshots/{snapshot_id}/expectations/{expectation_id}/decisions")
def decision_history(
    snapshot_id: str,
    expectation_id: str,
    request: Request,
    after: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> dict[str, object]:
    _, _, ref = _access(snapshot_id, request)
    from code_intelligence.models import IntelligenceError

    try:
        items = build_service().decision_history(ref, expectation_id, after=after, limit=limit)
    except IntelligenceError as exc:
        _raise_intelligence(exc)
    return {
        "items": [item.model_dump(mode="json") for item in items],
        "next_cursor": str(items[-1].revision) if len(items) == limit else None,
    }


@router.get("/snapshots/{snapshot_id}/regressions")
def regressions(snapshot_id: str, request: Request) -> dict[str, object]:
    _, _, ref = _access(snapshot_id, request)
    return {
        "items": [
            item.model_dump(mode="json") for item in build_service().verified_regressions(ref)
        ],
        "next_cursor": None,
    }


@router.post("/intelligence/context", response_model=ContextPack)
def context(body: ContextPackRequest, request: Request) -> ContextPack:
    _, _, ref = _access(body.snapshot_ref.snapshot_id, request)
    if body.snapshot_ref != ref:
        raise ApiError(
            ErrorCode.VALIDATION_FAILED, "Context request does not match exact snapshot", 422
        )
    from code_intelligence.models import IntelligenceError

    try:
        return build_service().build_context_pack(body)
    except IntelligenceError as exc:
        if "BUDGET_EXHAUSTED" in str(exc):
            raise ApiError(ErrorCode.BUDGET_EXHAUSTED, "Context budget too small", 422) from exc
        _raise_intelligence(exc)
