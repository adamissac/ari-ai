"""Append-only authenticated decisions and verified candidate regression memory."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "expectation_decisions",
        sa.Column("ref_key", sa.String(64), nullable=False),
        sa.Column("expectation_id", sa.String(80), nullable=False),
        sa.Column("revision", sa.Integer, nullable=False),
        sa.Column("snapshot_id", sa.String(80), sa.ForeignKey("snapshots.id"), nullable=False),
        sa.Column("decided_by", sa.String(80), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("doc", JSONB, nullable=False),
        sa.PrimaryKeyConstraint("ref_key", "expectation_id", "revision"),
        sa.CheckConstraint("revision >= 1", name="positive_decision_revision"),
    )
    op.create_table(
        "verified_regression_memory",
        sa.Column(
            "patch_id", sa.String(80), sa.ForeignKey("patch_candidates.id"), primary_key=True
        ),
        sa.Column("snapshot_id", sa.String(80), sa.ForeignKey("snapshots.id"), nullable=False),
        sa.Column(
            "verification_id",
            sa.String(80),
            sa.ForeignKey("verification_results.id"),
            nullable=False,
        ),
        sa.Column("ref_key", sa.String(64), nullable=False),
        sa.Column("doc", JSONB, nullable=False),
    )
    op.create_index(
        "ix_verified_regression_memory_ref_key", "verified_regression_memory", ["ref_key"]
    )
    # Application roles may append and read; accidental UPDATE/DELETE must fail.
    op.execute("""CREATE FUNCTION protect_intelligence_memory() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'intelligence memory is append-only'; END;
        $$ LANGUAGE plpgsql""")
    for table in ("expectation_decisions", "verified_regression_memory"):
        op.execute(f"""CREATE TRIGGER {table}_append_only BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION protect_intelligence_memory()""")


def downgrade() -> None:
    op.drop_table("verified_regression_memory")
    op.drop_table("expectation_decisions")
    op.execute("DROP FUNCTION protect_intelligence_memory()")
