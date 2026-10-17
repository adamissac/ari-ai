"""github_repo_access: repositories a signed-in user can reach through the GitHub App

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "github_repo_access",
        sa.Column("user_id", sa.String(80), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("installation_id", sa.BigInteger, nullable=False),
        sa.Column("default_branch", sa.String(200), nullable=False),
        sa.Column("private", sa.Boolean, nullable=False),
        sa.Column(
            "refreshed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("user_id", "full_name"),
    )


def downgrade() -> None:
    op.drop_table("github_repo_access")
