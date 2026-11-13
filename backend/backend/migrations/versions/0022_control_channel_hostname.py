"""Production applications: environment value and hostname control channels.

A connected application may now declare ``production``. Production applications register
an https control endpoint by hostname (up to 253 characters); the loopback fixture keeps
writing ``127.0.0.1``.
"""

import sqlalchemy as sa
from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


CK = "ck_connected_applications_environment"
HOST_CK = "ck_control_channels_control_channel_host"
PORT_CK = "ck_control_channels_control_channel_port"
# The loopback-only rule moves from the database to the gate and adapter, which check the
# channel against the application's environment on every call.
HOST_RULE = "host <> ''"
PORT_RULE = "port >= 1 AND port <= 65535 AND (host <> '127.0.0.1' OR port >= 1024)"


def upgrade() -> None:
    op.drop_constraint(op.f(CK), "connected_applications", type_="check")
    op.create_check_constraint(
        op.f(CK), "connected_applications", "environment in ('sandbox','owned_test','production')"
    )
    op.alter_column("control_channels", "host", type_=sa.String(253), existing_type=sa.String(16))
    op.drop_constraint(op.f(HOST_CK), "control_channels", type_="check")
    op.drop_constraint(op.f(PORT_CK), "control_channels", type_="check")
    op.create_check_constraint(op.f(HOST_CK), "control_channels", HOST_RULE)
    op.create_check_constraint(op.f(PORT_CK), "control_channels", PORT_RULE)


def downgrade() -> None:
    # Fails while a production application or a hostname longer than 16 characters exists.
    op.drop_constraint(op.f(CK), "connected_applications", type_="check")
    op.create_check_constraint(
        op.f(CK), "connected_applications", "environment in ('sandbox','owned_test')"
    )
    op.drop_constraint(op.f(HOST_CK), "control_channels", type_="check")
    op.drop_constraint(op.f(PORT_CK), "control_channels", type_="check")
    op.create_check_constraint(op.f(HOST_CK), "control_channels", "host = '127.0.0.1'")
    op.create_check_constraint(op.f(PORT_CK), "control_channels", "port >= 1024 AND port <= 65535")
    op.alter_column("control_channels", "host", type_=sa.String(16), existing_type=sa.String(253))
