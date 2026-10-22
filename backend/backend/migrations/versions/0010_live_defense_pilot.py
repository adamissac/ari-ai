"""Live Defense shadow-pilot tables: staging apps, ingest metadata, analyst reviews."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "connected_applications",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("project_id", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("environment", sa.String(length=20), nullable=False),
        sa.Column("created_by", sa.String(length=80), nullable=False),
        sa.Column("doc", JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "environment in ('sandbox','owned_test')",
            name=op.f("ck_connected_applications_environment"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name=op.f("fk_connected_applications_created_by_users")
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_connected_applications_project_id_projects"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_connected_applications")),
    )
    op.create_index(
        op.f("ix_connected_applications_project_id"),
        "connected_applications",
        ["project_id"],
        unique=False,
    )
    op.add_column(
        "ingest_tokens", sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("ingest_tokens", sa.Column("application_id", sa.String(length=80), nullable=True))
    op.create_foreign_key(
        op.f("fk_ingest_tokens_application_id_connected_applications"),
        "ingest_tokens",
        "connected_applications",
        ["application_id"],
        ["id"],
    )
    op.add_column(
        "runtime_windows", sa.Column("application_id", sa.String(length=80), nullable=True)
    )
    op.create_foreign_key(
        op.f("fk_runtime_windows_application_id_connected_applications"),
        "runtime_windows",
        "connected_applications",
        ["application_id"],
        ["id"],
    )
    op.create_table(
        "analyst_reviews",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("project_id", sa.String(length=80), nullable=False),
        sa.Column("recommendation_id", sa.String(length=80), nullable=False),
        sa.Column("decision", sa.String(length=40), nullable=False),
        sa.Column("reviewed_by", sa.String(length=80), nullable=False),
        sa.Column("doc", JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "decision in ('accept','reject','needs_investigation')",
            name=op.f("ck_analyst_reviews_decision"),
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_analyst_reviews_project_id_projects")
        ),
        sa.ForeignKeyConstraint(
            ["recommendation_id"],
            ["defense_recommendations.id"],
            name=op.f("fk_analyst_reviews_recommendation_id_defense_recommendations"),
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by"], ["users.id"], name=op.f("fk_analyst_reviews_reviewed_by_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analyst_reviews")),
    )
    op.create_index(
        op.f("ix_analyst_reviews_project_id"), "analyst_reviews", ["project_id"], unique=False
    )
    op.create_index(
        op.f("ix_analyst_reviews_recommendation_id"),
        "analyst_reviews",
        ["recommendation_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_analyst_reviews_recommendation_id"), table_name="analyst_reviews")
    op.drop_index(op.f("ix_analyst_reviews_project_id"), table_name="analyst_reviews")
    op.drop_table("analyst_reviews")
    op.drop_constraint(
        op.f("fk_runtime_windows_application_id_connected_applications"),
        "runtime_windows",
        type_="foreignkey",
    )
    op.drop_column("runtime_windows", "application_id")
    op.drop_constraint(
        op.f("fk_ingest_tokens_application_id_connected_applications"),
        "ingest_tokens",
        type_="foreignkey",
    )
    op.drop_column("ingest_tokens", "application_id")
    op.drop_column("ingest_tokens", "last_used_at")
    op.drop_index(op.f("ix_connected_applications_project_id"), table_name="connected_applications")
    op.drop_table("connected_applications")
