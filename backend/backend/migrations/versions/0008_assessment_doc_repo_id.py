"""Backfill Assessment.repo_id (contracts 0.11) into existing assessment documents.

The ``assessments.repo_id`` column has always been NOT NULL; only the JSON document
lacked it. Data-only and idempotent; downgrade removes the key again.

Revision ID: 0008
Revises: 0007
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE assessments SET doc = jsonb_set(doc, '{repo_id}', to_jsonb(repo_id)) "
            "WHERE doc->>'repo_id' IS NULL"
        )
    )


def downgrade() -> None:
    op.execute(sa.text("UPDATE assessments SET doc = doc - 'repo_id'"))
