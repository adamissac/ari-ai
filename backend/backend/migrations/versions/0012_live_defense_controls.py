"""Live Defense Phase 4: grants, control channels, live_controls, emergency stops."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "control_grants",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("project_id", sa.String(length=80), nullable=False),
        sa.Column("application_id", sa.String(length=80), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
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
            name=op.f("fk_control_grants_application_id_connected_applications"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name=op.f("fk_control_grants_created_by_users")
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_control_grants_project_id_projects")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_control_grants")),
    )
    op.create_index(op.f("ix_control_grants_project_id"), "control_grants", ["project_id"])
    op.create_index(op.f("ix_control_grants_application_id"), "control_grants", ["application_id"])

    op.create_table(
        "control_channels",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("project_id", sa.String(length=80), nullable=False),
        sa.Column("application_id", sa.String(length=80), nullable=False),
        sa.Column("host", sa.String(length=16), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("hmac_secret", sa.String(length=200), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(length=80), nullable=False),
        sa.Column("doc", JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "host = '127.0.0.1'", name=op.f("ck_control_channels_control_channel_host")
        ),
        sa.CheckConstraint(
            "port >= 1024 AND port <= 65535",
            name=op.f("ck_control_channels_control_channel_port"),
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["connected_applications.id"],
            name=op.f("fk_control_channels_application_id_connected_applications"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name=op.f("fk_control_channels_created_by_users")
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_control_channels_project_id_projects")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_control_channels")),
    )
    op.create_index(op.f("ix_control_channels_project_id"), "control_channels", ["project_id"])
    op.create_index(
        op.f("ix_control_channels_application_id"), "control_channels", ["application_id"]
    )
    op.create_index(
        "uq_control_channels_active_app",
        "control_channels",
        ["application_id"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )

    op.create_table(
        "live_controls",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("project_id", sa.String(length=80), nullable=False),
        sa.Column("application_id", sa.String(length=80), nullable=False),
        sa.Column("live_policy_decision_id", sa.String(length=80), nullable=True),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("unresolved", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("binding_sha256", sa.String(length=64), nullable=False),
        sa.Column("doc", JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "kind in ('rate_limit','block_source','increase_logging','escalate')",
            name=op.f("ck_live_controls_live_control_kind"),
        ),
        sa.CheckConstraint(
            "status in ('pending_authorization','authorized','executing','verifying',"
            "'verified','failed','expired','rolled_back','escalated','rejected',"
            "'emergency_stopped')",
            name=op.f("ck_live_controls_live_control_status"),
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["connected_applications.id"],
            name=op.f("fk_live_controls_application_id_connected_applications"),
        ),
        sa.ForeignKeyConstraint(
            ["live_policy_decision_id"],
            ["live_policy_decisions.id"],
            name=op.f("fk_live_controls_live_policy_decision_id_live_policy_decisions"),
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_live_controls_project_id_projects")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_live_controls")),
    )
    op.create_index(op.f("ix_live_controls_project_id"), "live_controls", ["project_id"])
    op.create_index(op.f("ix_live_controls_application_id"), "live_controls", ["application_id"])
    op.create_index(op.f("ix_live_controls_status"), "live_controls", ["status"])

    op.create_table(
        "emergency_stops",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("project_id", sa.String(length=80), nullable=False),
        sa.Column("application_id", sa.String(length=80), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("requested_by", sa.String(length=80), nullable=False),
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
            name=op.f("fk_emergency_stops_application_id_connected_applications"),
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_emergency_stops_project_id_projects")
        ),
        sa.ForeignKeyConstraint(
            ["requested_by"], ["users.id"], name=op.f("fk_emergency_stops_requested_by_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_emergency_stops")),
    )
    op.create_index(op.f("ix_emergency_stops_project_id"), "emergency_stops", ["project_id"])
    op.create_index(
        "uq_emergency_stops_active_project",
        "emergency_stops",
        ["project_id"],
        unique=True,
        postgresql_where=sa.text("active IS TRUE AND application_id IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_emergency_stops_active_project", table_name="emergency_stops")
    op.drop_index(op.f("ix_emergency_stops_project_id"), table_name="emergency_stops")
    op.drop_table("emergency_stops")
    op.drop_index(op.f("ix_live_controls_status"), table_name="live_controls")
    op.drop_index(op.f("ix_live_controls_application_id"), table_name="live_controls")
    op.drop_index(op.f("ix_live_controls_project_id"), table_name="live_controls")
    op.drop_table("live_controls")
    op.drop_index("uq_control_channels_active_app", table_name="control_channels")
    op.drop_index(op.f("ix_control_channels_application_id"), table_name="control_channels")
    op.drop_index(op.f("ix_control_channels_project_id"), table_name="control_channels")
    op.drop_table("control_channels")
    op.drop_index(op.f("ix_control_grants_application_id"), table_name="control_grants")
    op.drop_index(op.f("ix_control_grants_project_id"), table_name="control_grants")
    op.drop_table("control_grants")
