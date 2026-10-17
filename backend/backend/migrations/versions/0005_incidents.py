"""Evidence-linked incident lifecycle.

Revision ID: 0005
Revises: 0004
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "incidents",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("project_id", sa.String(80), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("phase", sa.String(40), nullable=False),
        sa.Column("doc", JSONB, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_incidents_project_id", "incidents", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_incidents_project_id", table_name="incidents")
    op.drop_table("incidents")
