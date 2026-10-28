"""Re-check a repository's GitHub connection right before each GitHub write.

A job that writes to GitHub (fix delivery, build-recipe PRs, PR review comments) can run
for minutes after it was queued. In that window the owner may disconnect the repository
(`repositories.disconnected_at`) or GitHub may detach the App installation
(`repositories.installation_id` cleared or replaced by a reconnect). The initial check at
job start does not cover that, so handlers call `require_connected` immediately before
minting a write token, pushing, opening a pull request, or posting a review.
"""

from __future__ import annotations

import sqlalchemy as sa

from backend.db import repositories, transaction


class RepositoryDetached(Exception):
    """The repository was disconnected or its installation detached after the job started."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def connection_problem(repo_id: str, installation_id: int) -> str | None:
    """None while `repo_id` is still connected through `installation_id`; else the reason."""
    with transaction() as conn:
        row = (
            conn.execute(
                sa.select(repositories.c.installation_id, repositories.c.disconnected_at).where(
                    repositories.c.id == repo_id
                )
            )
            .mappings()
            .first()
        )
    if row is None:
        return "repository no longer exists"
    if row["disconnected_at"] is not None:
        return "repository is disconnected"
    if row["installation_id"] is None:
        return "GitHub App installation was detached"
    if int(row["installation_id"]) != installation_id:
        return "repository installation changed"
    return None


def require_connected(repo_id: str, installation_id: int) -> None:
    reason = connection_problem(repo_id, installation_id)
    if reason is not None:
        raise RepositoryDetached(reason)
