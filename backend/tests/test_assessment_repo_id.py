"""Contracts 0.11: Assessment.repo_id is always set by the backend and backfilled into
older documents (migration 0008), so findings link source lines without guessing."""

from __future__ import annotations

import importlib

import sqlalchemy as sa
from helpers import setup_project

from backend.db import assessments, transaction


def test_assessment_carries_its_repository_and_old_docs_are_backfilled(client_factory) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)
    created = alice.post(
        f"/api/v1/projects/{ids['project']}/assessments",
        json={"scope_id": ids["scope"], "repo_id": ids["repo"], "commit_sha": "b" * 40},
    ).json()["assessment"]
    assert created["repo_id"] == ids["repo"]
    asm = created["id"]
    assert alice.get(f"/api/v1/assessments/{asm}").json()["assessment"]["repo_id"] == ids["repo"]

    # A document written before 0.11 has no repo_id; the migration's SQL fills it from the column.
    with transaction() as conn:
        conn.execute(
            sa.update(assessments)
            .where(assessments.c.id == asm)
            .values(doc=assessments.c.doc - "repo_id")
        )
    assert alice.get(f"/api/v1/assessments/{asm}").json()["assessment"]["repo_id"] is None
    mig = importlib.import_module("backend.migrations.versions.0008_assessment_doc_repo_id")
    with transaction() as conn:
        conn.execute(
            sa.text(
                "UPDATE assessments SET doc = jsonb_set(doc, '{repo_id}', to_jsonb(repo_id)) "
                "WHERE doc->>'repo_id' IS NULL"
            )
        )
    assert "jsonb_set(doc, '{repo_id}'" in open(mig.__file__).read()  # same statement
    assert alice.get(f"/api/v1/assessments/{asm}").json()["assessment"]["repo_id"] == ids["repo"]
