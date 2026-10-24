"""Populated 0015->0016 upgrade proof on a disposable local PostgreSQL database."""

import uuid

import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from conftest import _admin_engine

from backend.migrate import MIGRATIONS


def test_0016_preserves_existing_jobs_and_backfills_project():
    admin = _admin_engine()
    name = "review_migration_" + uuid.uuid4().hex[:12]
    with admin.connect() as conn:
        conn.execute(sa.text(f'CREATE DATABASE "{name}"'))
    engine = sa.create_engine(admin.url.set(database=name))
    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS))
    try:
        with engine.begin() as conn:
            cfg.attributes["connection"] = conn
            command.upgrade(cfg, "0015")
            for state in ["queued", "running", "succeeded", "cancelled"]:
                conn.execute(
                    sa.text(
                        "INSERT INTO jobs(id,kind,payload,status) "
                        "VALUES (:id,'review_fixture',CAST(:payload AS jsonb),:state)"
                    ),
                    {
                        "id": "review_" + state,
                        "payload": '{"project_id":"prj_owned_fixture"}',
                        "state": state,
                    },
                )
            command.upgrade(cfg, "0016")
            rows = conn.execute(sa.text("SELECT id,status,project_id FROM jobs ORDER BY id")).all()
            assert len(rows) == 4
            assert all(
                r.id == "review_" + r.status and r.project_id == "prj_owned_fixture" for r in rows
            )
            assert (
                conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one()
                == "0016"
            )
            command.downgrade(cfg, "0015")
            assert conn.execute(sa.text("SELECT count(*) FROM jobs")).scalar_one() == 4
            command.upgrade(cfg, "0016")
            assert (
                conn.execute(
                    sa.text("SELECT count(*) FROM jobs WHERE project_id='prj_owned_fixture'")
                ).scalar_one()
                == 4
            )
    finally:
        engine.dispose()
        with admin.connect() as conn:
            conn.execute(sa.text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()
