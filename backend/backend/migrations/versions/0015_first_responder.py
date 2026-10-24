"""Live Defense Phase 7A: first-responder modes, decisions, mappings, handoffs."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "first_responder_modes",
        sa.Column("project_id", sa.String(length=80), nullable=False),
        sa.Column("intent", sa.String(length=40), nullable=False),
        sa.Column("updated_by", sa.String(length=80), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("doc", JSONB(), nullable=False),
        sa.CheckConstraint(
            "intent in ('off','monitor','assisted_response')",
            name=op.f("ck_first_responder_modes_first_responder_intent"),
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_first_responder_modes_project_id_projects"),
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["users.id"], name=op.f("fk_first_responder_modes_updated_by_users")
        ),
        sa.PrimaryKeyConstraint("project_id", name=op.f("pk_first_responder_modes")),
    )
    op.create_table(
        "deploy_commit_mappings",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("project_id", sa.String(length=80), nullable=False),
        sa.Column("application_id", sa.String(length=80), nullable=False),
        sa.Column("repo_id", sa.String(length=80), nullable=False),
        sa.Column("commit_sha", sa.String(length=40), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(length=80), nullable=False),
        sa.Column("doc", JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["connected_applications.id"],
            name=op.f("fk_deploy_commit_mappings_application_id_connected_applications"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name=op.f("fk_deploy_commit_mappings_created_by_users")
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_deploy_commit_mappings_project_id_projects"),
        ),
        sa.ForeignKeyConstraint(
            ["repo_id"],
            ["repositories.id"],
            name=op.f("fk_deploy_commit_mappings_repo_id_repositories"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_deploy_commit_mappings")),
    )
    op.create_index(
        op.f("ix_deploy_commit_mappings_project_id"), "deploy_commit_mappings", ["project_id"]
    )
    op.create_index(
        op.f("ix_deploy_commit_mappings_application_id"),
        "deploy_commit_mappings",
        ["application_id"],
    )
    op.create_table(
        "first_responder_decisions",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("project_id", sa.String(length=80), nullable=False),
        sa.Column("application_id", sa.String(length=80), nullable=True),
        sa.Column("dedupe_key", sa.String(length=400), nullable=False),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("doc", JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["connected_applications.id"],
            name=op.f("fk_first_responder_decisions_application_id_connected_applications"),
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_first_responder_decisions_project_id_projects"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_first_responder_decisions")),
        sa.UniqueConstraint("dedupe_key", name=op.f("uq_first_responder_decisions_dedupe_key")),
    )
    op.create_index(
        op.f("ix_first_responder_decisions_project_id"),
        "first_responder_decisions",
        ["project_id"],
    )
    op.create_table(
        "first_responder_invocations",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("decision_id", sa.String(length=80), nullable=False),
        sa.Column("project_id", sa.String(length=80), nullable=False),
        sa.Column("agent", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("doc", JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["decision_id"],
            ["first_responder_decisions.id"],
            name=op.f("fk_first_responder_invocations_decision_id_first_responder_decisions"),
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_first_responder_invocations_project_id_projects"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_first_responder_invocations")),
    )
    op.create_index(
        op.f("ix_first_responder_invocations_decision_id"),
        "first_responder_invocations",
        ["decision_id"],
    )
    op.create_index(
        op.f("ix_first_responder_invocations_project_id"),
        "first_responder_invocations",
        ["project_id"],
    )
    op.create_table(
        "analyst_handoffs",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("project_id", sa.String(length=80), nullable=False),
        sa.Column("application_id", sa.String(length=80), nullable=True),
        sa.Column("decision_id", sa.String(length=80), nullable=False),
        sa.Column("state", sa.String(length=40), nullable=False),
        sa.Column("confirmation", sa.String(length=20), nullable=False),
        sa.Column("created_by", sa.String(length=80), nullable=False),
        sa.Column("doc", JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["connected_applications.id"],
            name=op.f("fk_analyst_handoffs_application_id_connected_applications"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name=op.f("fk_analyst_handoffs_created_by_users")
        ),
        sa.ForeignKeyConstraint(
            ["decision_id"],
            ["first_responder_decisions.id"],
            name=op.f("fk_analyst_handoffs_decision_id_first_responder_decisions"),
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_analyst_handoffs_project_id_projects")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analyst_handoffs")),
    )
    op.create_index(op.f("ix_analyst_handoffs_project_id"), "analyst_handoffs", ["project_id"])
    op.create_index(op.f("ix_analyst_handoffs_decision_id"), "analyst_handoffs", ["decision_id"])


def downgrade() -> None:
    op.drop_table("analyst_handoffs")
    op.drop_table("first_responder_invocations")
    op.drop_table("first_responder_decisions")
    op.drop_table("deploy_commit_mappings")
    op.drop_table("first_responder_modes")
