"""Phase 7A first-responder API. Mode changes are owner-only, authenticated, audited."""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from fastapi import APIRouter, Request

from backend import audit
from backend.api.deps import ApiError, not_found, require_project, require_user
from backend.api.live_defense import _load_application
from backend.db import (
    analyst_handoffs,
    deploy_commit_mappings,
    first_responder_decisions,
    first_responder_invocations,
    repositories,
    transaction,
)
from backend.live_defense.capabilities import load_registry
from backend.live_defense.first_responder import reconcile_off
from backend.live_defense.modes import (
    effective_permissions,
    independently_authorized_control_jobs,
    load_intent,
    save_intent,
)
from shared.audit import ActorType
from shared.errors import ErrorCode
from shared.ids import IdPrefix, new_id
from shared.live_defense import (
    AnalystHandoff,
    AnalystHandoffDeliveryAck,
    AnalystHandoffState,
    DeployCommitMapping,
    DeployCommitMappingCreate,
    FirstResponderDecision,
    FirstResponderIntent,
    FirstResponderInvocation,
    FirstResponderModeUpdate,
)
from shared.tenancy import MemberRole

router = APIRouter(tags=["live-defense-first-responder"])


@router.get("/projects/{project_id}/first-responder/mode")
def get_mode(project_id: str, request: Request) -> dict[str, Any]:
    with transaction() as conn:
        require_project(conn, require_user(conn, request), project_id)
        return load_intent(conn, project_id).model_dump(mode="json")


@router.post("/projects/{project_id}/first-responder/mode")
def put_mode(project_id: str, body: FirstResponderModeUpdate, request: Request) -> dict[str, Any]:
    with transaction() as conn:
        user = require_user(conn, request)
        org_id, _ = require_project(conn, user, project_id, MemberRole.owner)
        view = save_intent(
            conn, project_id=project_id, intent=body.intent, actor_id=user.id, note=body.note
        )
        cancelled = 0
        leftover = 0
        if body.intent is FirstResponderIntent.off:
            cancelled = reconcile_off(conn, project_id)["cancelled_first_responder_jobs"]
            leftover = independently_authorized_control_jobs(conn, project_id)
        audit.record(
            conn,
            org_id=org_id,
            project_id=project_id,
            actor_type=ActorType.user,
            actor_id=user.id,
            action="live_defense.first_responder.mode",
            subject_type="project",
            subject_id=project_id,
            details={
                "intent": body.intent.value,
                "previous_intent": view.previous_intent.value if view.previous_intent else None,
                "stop_kind": view.stop_kind.value,
                "cancelled_first_responder_jobs": cancelled,
                "independently_authorized_control_jobs": leftover,
                "retention_policy_unchanged": True,
                "auto_execute": False,
                "note": body.note,
            },
        )
        return view.model_copy(
            update={
                "cancelled_first_responder_jobs": cancelled,
                "independently_authorized_control_jobs": leftover,
            }
        ).model_dump(mode="json")


@router.get("/applications/{app_id}/first-responder/permissions")
def get_permissions(app_id: str, request: Request) -> dict[str, Any]:
    with transaction() as conn:
        user = require_user(conn, request)
        app = _load_application(conn, app_id)
        require_project(conn, user, app.project_id)
        mapping = (
            conn.execute(
                sa.select(deploy_commit_mappings.c.id).where(
                    deploy_commit_mappings.c.application_id == app_id,
                    deploy_commit_mappings.c.revoked_at.is_(None),
                )
            ).scalar()
            is not None
        )
        repo_id = conn.execute(
            sa.select(deploy_commit_mappings.c.repo_id)
            .where(
                deploy_commit_mappings.c.application_id == app_id,
                deploy_commit_mappings.c.revoked_at.is_(None),
            )
            .limit(1)
        ).scalar()
        return effective_permissions(
            conn,
            project_id=app.project_id,
            application=app,
            repo_id=repo_id,
            trusted_mapping=mapping,
        ).model_dump(mode="json")


@router.get("/projects/{project_id}/first-responder/capabilities")
def get_capabilities(project_id: str, request: Request) -> dict[str, Any]:
    with transaction() as conn:
        require_project(conn, require_user(conn, request), project_id)
        return load_registry().model_dump(mode="json")


@router.get("/projects/{project_id}/first-responder/decisions")
def list_decisions(project_id: str, request: Request) -> dict[str, Any]:
    with transaction() as conn:
        require_project(conn, require_user(conn, request), project_id)
        rows = (
            conn.execute(
                sa.select(first_responder_decisions.c.doc)
                .where(first_responder_decisions.c.project_id == project_id)
                .order_by(first_responder_decisions.c.created_at.desc())
            )
            .scalars()
            .all()
        )
        items = [FirstResponderDecision.model_validate(doc).model_dump(mode="json") for doc in rows]
        return {
            "items": items,
            "next_cursor": None,
            "label": "Deterministic first-responder decisions. Not executed. Not RL labels.",
        }


@router.get("/projects/{project_id}/first-responder/invocations")
def list_invocations(project_id: str, request: Request) -> dict[str, Any]:
    with transaction() as conn:
        require_project(conn, require_user(conn, request), project_id)
        rows = (
            conn.execute(
                sa.select(first_responder_invocations.c.doc)
                .where(first_responder_invocations.c.project_id == project_id)
                .order_by(first_responder_invocations.c.created_at.desc())
            )
            .scalars()
            .all()
        )
        items = [
            FirstResponderInvocation.model_validate(doc).model_dump(mode="json") for doc in rows
        ]
        return {"items": items, "next_cursor": None}


@router.get("/projects/{project_id}/first-responder/handoffs")
def list_handoffs(project_id: str, request: Request) -> dict[str, Any]:
    with transaction() as conn:
        require_project(conn, require_user(conn, request), project_id)
        rows = (
            conn.execute(
                sa.select(analyst_handoffs.c.doc)
                .where(analyst_handoffs.c.project_id == project_id)
                .order_by(analyst_handoffs.c.created_at.desc())
            )
            .scalars()
            .all()
        )
        items = [AnalystHandoff.model_validate(doc).model_dump(mode="json") for doc in rows]
        return {"items": items, "next_cursor": None}


@router.post("/applications/{app_id}/deploy-mappings", status_code=201)
def create_mapping(
    app_id: str, body: DeployCommitMappingCreate, request: Request
) -> dict[str, Any]:
    with transaction() as conn:
        user = require_user(conn, request)
        app = _load_application(conn, app_id)
        org_id, _ = require_project(conn, user, app.project_id, MemberRole.owner)
        repo = conn.execute(
            sa.select(repositories.c.id, repositories.c.project_id).where(
                repositories.c.id == body.repo_id
            )
        ).first()
        if repo is None or repo.project_id != app.project_id:
            raise not_found("repository")
        mapping = DeployCommitMapping(
            id=new_id(IdPrefix.dcm),
            project_id=app.project_id,
            application_id=app_id,
            repo_id=body.repo_id,
            commit_sha=body.commit_sha,
            deployed_at=body.deployed_at,
            created_by=user.id,
            created_at=body.deployed_at,
        )
        conn.execute(
            sa.insert(deploy_commit_mappings).values(
                id=mapping.id,
                project_id=mapping.project_id,
                application_id=app_id,
                repo_id=body.repo_id,
                commit_sha=body.commit_sha,
                created_by=user.id,
                doc=mapping.model_dump(mode="json"),
            )
        )
        audit.record(
            conn,
            org_id=org_id,
            project_id=app.project_id,
            actor_type=ActorType.user,
            actor_id=user.id,
            action="live_defense.deploy_mapping.created",
            subject_type="deploy_commit_mapping",
            subject_id=mapping.id,
            details={"commit_sha": body.commit_sha, "source": "owner_attested"},
        )
        return mapping.model_dump(mode="json")


@router.post("/first-responder/handoffs/{handoff_id}/delivery-ack")
def ack_delivery(
    handoff_id: str, body: AnalystHandoffDeliveryAck, request: Request
) -> dict[str, Any]:
    with transaction() as conn:
        user = require_user(conn, request)
        row = (
            conn.execute(sa.select(analyst_handoffs).where(analyst_handoffs.c.id == handoff_id))
            .mappings()
            .first()
        )
        if row is None:
            raise not_found("handoff")
        org_id, _ = require_project(conn, user, row["project_id"], MemberRole.owner)
        current = AnalystHandoff.model_validate(row["doc"])
        updated = current.model_copy(
            update={
                "state": AnalystHandoffState.delivered,
                "delivery_provider": body.provider,
                "delivery_provider_message_id": body.provider_message_id,
                "delivery_confirmed_at": body.received_at,
            }
        )
        conn.execute(
            sa.update(analyst_handoffs)
            .where(analyst_handoffs.c.id == handoff_id)
            .values(state=updated.state.value, doc=updated.model_dump(mode="json"))
        )
        audit.record(
            conn,
            org_id=org_id,
            project_id=row["project_id"],
            actor_type=ActorType.user,
            actor_id=user.id,
            action="live_defense.handoff.delivered",
            subject_type="analyst_handoff",
            subject_id=handoff_id,
            details={"provider": body.provider, "provider_message_id": body.provider_message_id},
        )
        return updated.model_dump(mode="json")


@router.post("/first-responder/handoffs/{handoff_id}/confirm")
def confirm_handoff(handoff_id: str, request: Request) -> dict[str, Any]:
    """Mark confirmed only from executed Probe evidence already stored — not LLM prose."""
    with transaction() as conn:
        user = require_user(conn, request)
        row = (
            conn.execute(sa.select(analyst_handoffs).where(analyst_handoffs.c.id == handoff_id))
            .mappings()
            .first()
        )
        if row is None:
            raise not_found("handoff")
        require_project(conn, user, row["project_id"], MemberRole.owner)
        current = AnalystHandoff.model_validate(row["doc"])
        inv = conn.execute(
            sa.select(first_responder_invocations.c.doc).where(
                first_responder_invocations.c.decision_id == current.decision_id,
                first_responder_invocations.c.agent == "probe",
                first_responder_invocations.c.status == "completed_unverified",
            )
        ).scalar()
        if inv is None:
            raise ApiError(
                ErrorCode.CONFLICT_STATE,
                "confirmation requires executed Probe evidence; LLM prose is not confirmation",
                409,
            )
        # Probe completed_unverified is still not confirmation. Refuse.
        raise ApiError(
            ErrorCode.CONFLICT_STATE,
            "Probe completed_unverified is not confirmation. Confirmed stays distinct.",
            409,
        )


# AUTO-EXECUTE is not a route. Absence is the control: OpenAPI must not list
# apply/execute/isolate paths (backend/tests/test_rl_no_action_path.py).
