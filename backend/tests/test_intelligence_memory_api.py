"""Real PostgreSQL + authenticated API; repository source is parsed, never run."""

from __future__ import annotations

import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
import sqlalchemy as sa
from helpers import add_member

from backend.db import get_engine, transaction
from backend.intel_store import PostgresPayloadStore
from backend.intelligence import build_service
from backend.intelligence_memory import PostgresMemoryStore
from code_intelligence.api import RepositoryBinding, create_service
from code_intelligence.memory import MemoryConflict
from shared.base import utcnow
from shared.intelligence_memory import ExpectationDecision


def _index(alice, tmp_path: Path):  # type: ignore[no-untyped-def]
    project = alice.post("/api/v1/projects", json={"name": "intelligence-memory"}).json()["id"]
    repo = alice.post(
        f"/api/v1/projects/{project}/repositories", json={"full_name": "owned/memory-fixture"}
    ).json()["id"]
    root = tmp_path / "repo"
    root.mkdir()
    (root / "app.py").write_text(
        'def read_payment(customer):\n    """A customer must only read their own payments."""\n    return customer\n'
    )

    def git(*args: str) -> str:
        return subprocess.check_output(
            [
                "git",
                "-C",
                str(root),
                "-c",
                "user.name=Fixture",
                "-c",
                "user.email=fixture@example.invalid",
                "-c",
                "commit.gpgsign=false",
                "-c",
                "core.hooksPath=/dev/null",
                *args,
            ],
            text=True,
        ).strip()

    git("init", "-q")
    git("add", ".")
    git("commit", "-qm", "fixture")
    sha = git("rev-parse", "HEAD")
    service = create_service(
        payload_store=PostgresPayloadStore(),
        repositories=[RepositoryBinding(project, repo, "owned/memory-fixture", root)],
    )
    ref = service.index_repository(project, repo, sha)
    exp = service.expectations(ref)[0]
    return service, ref, exp


def test_authenticated_decisions_are_atomic_audited_and_visible_after_restart(
    client_factory, tmp_path: Path
) -> None:  # type: ignore[no-untyped-def]
    alice, eve = client_factory("memory-alice"), client_factory("memory-eve")
    service, ref, exp = _index(alice, tmp_path)
    url = f"/api/v1/snapshots/{ref.snapshot_id}/expectations/{exp.id}"
    body = {
        "status": "confirmed",
        "reason": "The product owner confirms the ownership rule",
        "expected_revision": 0,
    }
    assert eve.patch(url, json=body).status_code == 404
    csrf = alice.headers.pop("X-CSRF-Token")
    assert alice.patch(url, json=body).status_code == 403
    alice.headers["X-CSRF-Token"] = csrf
    assert alice.patch(url, json={**body, "decided_by": eve.me["user"]["id"]}).status_code == 422
    response = alice.patch(url, json=body)
    assert response.status_code == 200, response.text
    assert response.json()["decided_by"] == alice.me["user"]["id"]
    assert response.json()["revision"] == 1
    assert alice.patch(url, json=body).json() == response.json()  # idempotent retry
    assert alice.patch(url, json={**body, "status": "rejected"}).status_code == 409
    current = build_service().expectations(ref)[0]
    assert current.status.value == "confirmed"
    assert current.sources[-1].kind.value == "human_input"
    assert service.store.get(ref).expectations[0].status.value != "confirmed"
    listed = alice.get(f"/api/v1/snapshots/{ref.snapshot_id}/expectations").json()["items"]
    assert listed[0]["status"] == "confirmed"
    history = alice.get(url + "/decisions?limit=1").json()
    assert history["items"][0]["revision"] == 1 and history["next_cursor"] == "1"
    assert alice.get(url + "/decisions?after=1").json()["items"] == []
    pack = alice.post(
        "/api/v1/intelligence/context",
        json={
            "snapshot_ref": ref.model_dump(mode="json"),
            "purpose": "scout",
            "focus": [exp.id],
            "token_budget": 24000,
        },
    )
    assert pack.status_code == 200, pack.text
    assert "product owner confirms" in pack.text
    mismatched = ref.model_copy(update={"commit_sha": "f" * 40})
    assert (
        alice.post(
            "/api/v1/intelligence/context",
            json={"snapshot_ref": mismatched.model_dump(mode="json"), "purpose": "review"},
        ).status_code
        == 422
    )
    with transaction() as conn:
        count = conn.execute(
            sa.text(
                "SELECT count(*) FROM audit_events WHERE doc->>'action'='expectation.decided' AND doc->>'subject_id'=:id"
            ),
            {"id": exp.id},
        ).scalar_one()
    assert count == 1
    with pytest.raises(sa.exc.DBAPIError, match="append-only"), get_engine().begin() as conn:
        conn.execute(sa.text("DELETE FROM expectation_decisions"))


def test_postgres_decision_race_cannot_overwrite_or_cross_snapshot(
    client_factory, tmp_path: Path
) -> None:  # type: ignore[no-untyped-def]
    alice, bob = client_factory("race-alice"), client_factory("race-bob")
    _, ref, exp = _index(alice, tmp_path)
    add_member(alice.me["memberships"][0]["organization"]["id"], bob.me["user"]["id"])
    store = PostgresMemoryStore()

    def save(actor: str) -> str:
        decision = ExpectationDecision(
            snapshot_ref=ref,
            expectation_id=exp.id,
            status="confirmed",
            reason="Concurrent authenticated decision",
            expected_revision=0,
            revision=1,
            decided_by=actor,
            decided_at=utcnow(),
        )
        try:
            store.put_decision(decision)
            return "saved"
        except MemoryConflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(save, [alice.me["user"]["id"], bob.me["user"]["id"]])) == [
            "conflict",
            "saved",
        ]
    assert len(store.decisions(ref)) == 1
    with pytest.raises(PermissionError):
        store.decisions(ref.model_copy(update={"project_id": "prj_wrong0000"}))
