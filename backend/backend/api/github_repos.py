"""Repository picker: what the signed-in user can connect through the GitHub App.

The list is captured at GitHub sign-in from the App's user-to-server token and stored
without the token (`github_repo_access`). Installing the App on more repositories sends
the user through sign-in again (GitHub "request user authorization during installation"),
which refreshes the list.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
import sqlalchemy as sa
from fastapi import APIRouter, Request
from sqlalchemy.engine import Connection

from backend.api.deps import ApiError, require_project, require_user
from backend.db import github_repo_access, repositories, transaction
from backend.github import GitHubApp, GitHubNotConfigured
from backend.settings import get_settings
from shared.errors import ErrorCode

log = logging.getLogger(__name__)

router = APIRouter(tags=["github"])


def store_repo_access(conn: Connection, user_id: str, repos: list[dict[str, Any]]) -> None:
    """Replace the user's accessible-repository list with `repos`."""
    conn.execute(sa.delete(github_repo_access).where(github_repo_access.c.user_id == user_id))
    seen: set[str] = set()
    rows = []
    for r in repos:
        if r["full_name"] in seen:
            continue
        seen.add(r["full_name"])
        rows.append({"user_id": user_id, **r})
    if rows:
        conn.execute(sa.insert(github_repo_access), rows)


def can_connect(conn: Connection, user_id: str, full_name: str, installation_id: int) -> bool:
    return (
        conn.execute(
            sa.select(github_repo_access.c.full_name).where(
                github_repo_access.c.user_id == user_id,
                github_repo_access.c.full_name == full_name,
                github_repo_access.c.installation_id == installation_id,
            )
        ).first()
        is not None
    )


@router.get("/github/repositories")
def list_accessible_repositories(request: Request) -> dict[str, Any]:
    """Repositories the user can connect, and whether each is already connected."""
    s = get_settings()
    with transaction() as conn:
        user = require_user(conn, request)
        rows = conn.execute(
            sa.select(github_repo_access, repositories.c.id.label("repo_id"))
            .join(
                repositories,
                repositories.c.full_name == github_repo_access.c.full_name,
                isouter=True,
            )
            .where(github_repo_access.c.user_id == user.id)
            .order_by(github_repo_access.c.full_name)
        ).mappings()
        items = [
            {
                "full_name": r["full_name"],
                "installation_id": r["installation_id"],
                "default_branch": r["default_branch"],
                "private": r["private"],
                "connected_repo_id": r["repo_id"],
            }
            for r in rows
        ]
    slug = s.github_app_slug
    return {
        "items": items,
        "install_url": f"{s.github_web_url}/apps/{slug}/installations/new" if slug else None,
        "next_cursor": None,
    }


@router.get("/repositories/{repo_id}/commits")
def recent_commits(repo_id: str, request: Request) -> dict[str, Any]:
    """Recent commits on the default branch, read live through the GitHub App installation."""
    with transaction() as conn:
        user = require_user(conn, request)
        repo = conn.execute(sa.select(repositories).where(repositories.c.id == repo_id)).first()
        if repo is None:
            raise ApiError(ErrorCode.NOT_FOUND, "repository not found", 404)
        require_project(conn, user, repo.project_id)
    if repo.installation_id is None:
        return {
            "items": [],
            "next_cursor": None,
            "available": False,
            "reason": "Connected by name, without the GitHub App, so commits cannot be read.",
        }
    try:
        items = GitHubApp().recent_commits(
            repo.installation_id, repo.full_name, repo.default_branch
        )
    except GitHubNotConfigured as exc:
        raise ApiError(
            ErrorCode.SUBSYSTEM_UNAVAILABLE, "GitHub App is not configured", 503
        ) from exc
    except httpx.HTTPError as exc:
        log.warning("listing commits for %s failed: %s", repo.full_name, type(exc).__name__)
        raise ApiError(
            ErrorCode.SUBSYSTEM_UNAVAILABLE, "GitHub did not return commits", 503
        ) from exc
    return {"items": items, "next_cursor": None, "available": True, "reason": None}
