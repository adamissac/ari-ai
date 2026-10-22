"""Live Defense Phase 3: live_policy_decisions + analyst reviews of shadow decisions."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "live_policy_decisions",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("project_id", sa.String(length=80), nullable=False),
        sa.Column("application_id", sa.String(length=80), nullable=True),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("producer", sa.String(length=20), nullable=False),
        sa.Column("inference_ran", sa.Boolean(), nullable=False),
        sa.Column("dedupe_key", sa.String(length=400), nullable=False),
        sa.Column("doc", JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "producer in ('rules','v6_shadow','abstention')",
            name=op.f("ck_live_policy_decisions_producer"),
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["connected_applications.id"],
            name=op.f("fk_live_policy_decisions_application_id_connected_applications"),
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_live_policy_decisions_project_id_projects"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_live_policy_decisions")),
        sa.UniqueConstraint("dedupe_key", name=op.f("uq_live_policy_decisions_dedupe_key")),
    )
    op.create_index(
        op.f("ix_live_policy_decisions_project_id"),
        "live_policy_decisions",
        ["project_id"],
        unique=False,
    )
    op.alter_column(
        "analyst_reviews",
        "recommendation_id",
        existing_type=sa.String(length=80),
        nullable=True,
    )
    op.add_column(
        "analyst_reviews",
        sa.Column("live_policy_decision_id", sa.String(length=80), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_analyst_reviews_live_policy_decision_id_live_policy_decisions"),
        "analyst_reviews",
        "live_policy_decisions",
        ["live_policy_decision_id"],
        ["id"],
    )
    op.create_check_constraint(
        "review_subject",
        "analyst_reviews",
        "(recommendation_id IS NOT NULL AND live_policy_decision_id IS NULL) "
        "OR (recommendation_id IS NULL AND live_policy_decision_id IS NOT NULL)",
    )
    op.create_index(
        op.f("ix_analyst_reviews_live_policy_decision_id"),
        "analyst_reviews",
        ["live_policy_decision_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_analyst_reviews_live_policy_decision_id"), table_name="analyst_reviews")
    op.drop_constraint(op.f("ck_analyst_reviews_review_subject"), "analyst_reviews", type_="check")
    op.drop_constraint(
        op.f("fk_analyst_reviews_live_policy_decision_id_live_policy_decisions"),
        "analyst_reviews",
        type_="foreignkey",
    )
    op.drop_column("analyst_reviews", "live_policy_decision_id")
    op.alter_column(
        "analyst_reviews",
        "recommendation_id",
        existing_type=sa.String(length=80),
        nullable=False,
    )
    op.drop_index(op.f("ix_live_policy_decisions_project_id"), table_name="live_policy_decisions")
    op.drop_table("live_policy_decisions")
