"""Automation stays off until owners opt in; migration pauses existing activity."""

import importlib

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from helpers import HEAD, setup_project

from backend.db import assessments, projects, repositories, transaction
from backend.services import create_assessment
from shared.assessment import AssessmentTrigger
from shared.tenancy import ProjectSettings, Repository, TriggerPolicy


def test_new_project_and_repository_start_off(client_factory):
    alice = client_factory("alice")
    p = alice.post("/api/v1/projects", json={"name": "opt-in"})
    assert p.status_code == 201
    assert p.json()["settings"]["monitoring_policy"]["enabled"] is False
    r = alice.post(
        f"/api/v1/projects/{p.json()['id']}/repositories",
        json={"full_name": "acme/opt-in", "installation_id": None},
    )
    assert r.status_code == 201
    assert r.json()["automatic_assessments"] is False
    assert ProjectSettings().monitoring_policy.enabled is False
    assert TriggerPolicy().enabled is False
    assert Repository.model_fields["automatic_assessments"].default is False


def test_pause_migration_resets_existing_switches_and_preserves_manual_runs(client_factory):
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)
    with transaction() as conn:
        auto, _ = create_assessment(
            conn,
            project_id=ids["project"],
            repo_id=ids["repo"],
            scope_id=ids["scope"],
            commit_sha=HEAD,
            trigger=AssessmentTrigger.monitoring,
            budget=None,
            created_by=None,
        )
        manual, _ = create_assessment(
            conn,
            project_id=ids["project"],
            repo_id=ids["repo"],
            scope_id=ids["scope"],
            commit_sha="c" * 40,
            trigger=AssessmentTrigger.manual,
            budget=None,
            created_by=alice.me["user"]["id"],
        )
        with Operations.context(MigrationContext.configure(conn)):
            importlib.import_module("backend.migrations.versions.0010_automation_opt_in").upgrade()
        assert conn.execute(sa.select(repositories.c.automatic_assessments)).scalar_one() is False
        settings = conn.execute(sa.select(projects.c.settings)).scalar_one()
        assert settings["monitoring_policy"]["enabled"] is False
        cancelled = dict(
            conn.execute(sa.select(assessments.c.id, assessments.c.cancel_requested)).all()
        )
        assert cancelled[auto.id] is True
        assert cancelled[manual.id] is False
    # An owner can explicitly opt back in after the one-time migration.
    assert (
        alice.patch(
            f"/api/v1/repositories/{ids['repo']}", json={"automatic_assessments": True}
        ).json()["automatic_assessments"]
        is True
    )
