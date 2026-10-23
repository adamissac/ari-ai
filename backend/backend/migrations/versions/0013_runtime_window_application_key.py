"""Runtime windows are unique per application, not just per project/source/route/time."""

from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("uq_runtime_windows_key", "runtime_windows", type_="unique")
    # coalesce: NULL application ids (project-token ingest) must still collide with each other
    op.execute(
        "CREATE UNIQUE INDEX uq_runtime_windows_key ON runtime_windows "
        "(project_id, source, route, window_end, (coalesce(application_id, '')))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX uq_runtime_windows_key")
    op.create_unique_constraint(
        "uq_runtime_windows_key",
        "runtime_windows",
        ["project_id", "source", "route", "window_end"],
    )
