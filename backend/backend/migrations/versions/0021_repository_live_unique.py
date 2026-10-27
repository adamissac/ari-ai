"""Repository names are unique among live rows only.

A disconnected repository row stays as history (assessments, findings and audit point at
it), but it must not lock the name forever: the global unique constraint meant a repository
one project had parked could never be connected by anyone else, even its new owner.
"""

from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("uq_repositories_provider_full_name", "repositories", type_="unique")
    op.create_index(
        "uq_repositories_live_full_name",
        "repositories",
        ["provider", "full_name"],
        unique=True,
        postgresql_where="disconnected_at IS NULL",
    )


def downgrade() -> None:
    # Fails while two rows share a name (one live, one parked); resolve those first.
    op.drop_index("uq_repositories_live_full_name", table_name="repositories")
    op.create_unique_constraint(
        "uq_repositories_provider_full_name", "repositories", ["provider", "full_name"]
    )
