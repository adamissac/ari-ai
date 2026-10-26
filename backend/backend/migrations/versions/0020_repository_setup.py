"""Repository setup: server-saved setup walkthrough progress per repository."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("repositories", sa.Column("setup", JSONB))


def downgrade() -> None:
    op.drop_column("repositories", "setup")
