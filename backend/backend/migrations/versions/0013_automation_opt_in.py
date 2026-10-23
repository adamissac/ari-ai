"""Reset automation OFF once; future changes require explicit owner opt-in.

Downgrade restores only the old column default, never resumes paid activity.
"""

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("repositories", "automatic_assessments", server_default=sa.false())
    op.execute("UPDATE repositories SET automatic_assessments = false")
    op.execute("""
        UPDATE projects SET settings = jsonb_set(
            settings, '{monitoring_policy}',
            COALESCE(settings->'monitoring_policy', '{}'::jsonb) || jsonb_build_object('enabled', false)
        )
    """)
    # Workers observe the existing cooperative cancellation flag at step boundaries.
    op.execute("""
        UPDATE assessments SET cancel_requested = true
        WHERE trigger = 'monitoring'
          AND state NOT IN ('COMPLETED', 'FAILED', 'CANCELLED', 'BUDGET_EXHAUSTED')
    """)
    # Wake delayed jobs so the normal handler finalizes their requests as skipped.
    op.execute("""
        UPDATE jobs SET run_after = now()
        WHERE kind = 'assess_github_commit' AND status = 'queued'
    """)


def downgrade() -> None:
    op.alter_column("repositories", "automatic_assessments", server_default=sa.true())
