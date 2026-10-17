"""HTTP reindexing respects producer versions and preserves historical snapshots."""

from dataclasses import replace

import pytest
import sqlalchemy as sa
from helpers import REPO, setup_project
from test_payload_store_intel_integration import two_commits as two_commits

from backend import worker
from backend.api import routes
from backend.db import jobs, snapshots, transaction
from backend.integrations import Loaded
from backend.intel_store import PostgresPayloadStore
from code_intelligence import ingest
from code_intelligence.api import RepositoryBinding, create_service


@pytest.mark.parametrize("change", ["parser", "prefix", "limits"])
def test_snapshot_request_reindexes_changed_version(
    client_factory, monkeypatch, two_commits, change
) -> None:
    alice, bob = client_factory("version-alice"), client_factory("version-bob")
    ids = setup_project(alice, bob)
    root, _, head, _ = two_commits
    binding = RepositoryBinding(ids["project"], ids["repo"], REPO, root)
    service = create_service(payload_store=PostgresPayloadStore(), repositories=[binding])
    old = service.index_repository(ids["project"], ids["repo"], head)
    original = alice.get(f"/api/v1/snapshots/{old.snapshot_id}").json()
    monkeypatch.setattr(routes, "load_factory", lambda _: Loaded(service, None))
    url = f"/api/v1/repositories/{ids['repo']}/snapshots"
    body = {"commit_sha": head}
    assert alice.post(url, json=body).json()["id"] == old.snapshot_id

    original_parser = ingest.INDEX_VERSION
    original_limits = service.limits
    if change == "parser":
        monkeypatch.setattr(ingest, "INDEX_VERSION", "test-parser-upgrade")
    elif change == "prefix":
        service.repositories[ids["repo"]] = replace(binding, include_prefix="payments_lite")
    else:
        service.limits = replace(service.limits, max_files=9999)

    response = alice.post(url, json=body)
    assert response.status_code == 202, response.text
    pending = response.json()
    assert pending["id"] != old.snapshot_id
    assert pending["status"] == "pending"
    assert alice.post(url, json=body).json()["id"] == pending["id"]
    # The real worker indexes the new snapshot through the same configured producer.
    monkeypatch.setattr("backend.pipeline.load_factory", lambda _: Loaded(service, None))
    worker.drain(kinds=["index_snapshot"])
    ready = alice.get(f"/api/v1/snapshots/{pending['id']}").json()
    assert ready["status"] == "ready", ready
    assert ready["index_version"] != old.index_version
    assert alice.post(url, json=body).json()["id"] == pending["id"]
    assert alice.get(f"/api/v1/snapshots/{old.snapshot_id}").json() == original
    # Rolling the configuration back reuses the older matching snapshot, rather
    # than creating a duplicate of its immutable version.
    monkeypatch.setattr(ingest, "INDEX_VERSION", original_parser)
    service.repositories[ids["repo"]] = binding
    service.limits = original_limits
    assert alice.post(url, json=body).json()["id"] == old.snapshot_id
    with transaction() as conn:
        assert (
            conn.execute(
                sa.select(sa.func.count()).select_from(jobs).where(jobs.c.kind == "index_snapshot")
            ).scalar_one()
            == 1
        )


def test_snapshot_ready_reuse_requires_available_version_provider(
    client_factory, monkeypatch
) -> None:
    alice, bob = client_factory("version-alice"), client_factory("version-bob")
    ids = setup_project(alice, bob)
    url = f"/api/v1/repositories/{ids['repo']}/snapshots"
    body = {"commit_sha": "a" * 40}
    pending = alice.post(url, json=body).json()
    with transaction() as conn:
        conn.execute(
            sa.update(snapshots)
            .where(snapshots.c.id == pending["id"])
            .values(status="ready", doc={**pending, "status": "ready", "index_version": "old"})
        )
    monkeypatch.setattr(routes, "load_factory", lambda _: Loaded(None, "unavailable"))
    response = alice.post(url, json=body)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "SUBSYSTEM_UNAVAILABLE"


def test_failed_snapshot_can_be_retried_without_loading_provider(
    client_factory, monkeypatch
) -> None:
    alice, bob = client_factory("version-alice"), client_factory("version-bob")
    eve = client_factory("version-eve")
    ids = setup_project(alice, bob)
    url = f"/api/v1/repositories/{ids['repo']}/snapshots"
    body = {"commit_sha": "a" * 40}
    pending = alice.post(url, json=body).json()
    with transaction() as conn:
        conn.execute(
            sa.update(snapshots)
            .where(snapshots.c.id == pending["id"])
            .values(status="failed", doc={**pending, "status": "failed"})
        )

    def unexpected_provider(_):
        pytest.fail("authorization and failed retries must not load the provider")

    monkeypatch.setattr(routes, "load_factory", unexpected_provider)
    assert eve.post(url, json=body).status_code == 404
    retried = alice.post(url, json=body)
    assert retried.status_code == 202
    assert retried.json()["id"] != pending["id"]
