"""Real PostgreSQL + authenticated API; repository source is parsed, never run."""

from __future__ import annotations

import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
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


def test_verified_candidate_outbox_is_durable_idempotent_and_retrieved(
    client_factory, tmp_path: Path
) -> None:  # type: ignore[no-untyped-def]
    from types import SimpleNamespace

    from backend import worker
    from backend.host import AssessmentHost, HostError
    from backend.intelligence_jobs import persist_verified_regression
    from shared.assessment import AgentName, AgentRunStatus
    from shared.evidence import EvidenceRef
    from shared.findings import (
        Finding,
        PatchCandidate,
        VerificationCheck,
        VerificationCheckName,
        VerificationResult,
    )

    alice, bob = client_factory("candidate-alice"), client_factory("candidate-bob")
    _, ref, _ = _index(alice, tmp_path)
    add_member(alice.me["memberships"][0]["organization"]["id"], bob.me["user"]["id"])
    scope = alice.post(
        f"/api/v1/projects/{ref.project_id}/scopes",
        json={
            "name": "Owned fixture scope",
            "targets": [{"repo_id": ref.repo_id, "build_recipe_ref": "fixture.json"}],
            "expires_at": (utcnow() + timedelta(days=1)).isoformat(),
        },
    ).json()["id"]
    assert bob.post(f"/api/v1/scopes/{scope}/approve").status_code == 200
    created = alice.post(
        f"/api/v1/projects/{ref.project_id}/assessments",
        headers={"Idempotency-Key": "memory-fixture"},
        json={
            "repo_id": ref.repo_id,
            "scope_id": scope,
            "commit_sha": ref.commit_sha,
            "snapshot_id": ref.snapshot_id,
        },
    )
    assert created.status_code == 202, created.text
    assessment_id = created.json()["assessment"]["id"]
    host = AssessmentHost(assessment_id)
    fixture_path = Path(__file__).resolve().parents[2] / "shared/fixtures/v0/Finding.json"
    finding = Finding.model_validate_json(fixture_path.read_text()).model_copy(
        update={
            "assessment_id": assessment_id,
            "commit_sha": ref.commit_sha,
        }
    )
    host.record_finding(finding, actor="fixture")
    patch_run = host.start_agent_run(
        AgentName.patch, "fixture:patch", provider_mode="fake", model_id=None, prompt_version=None
    )
    verify_run = host.start_agent_run(
        AgentName.verify, "fixture:verify", provider_mode="fake", model_id=None, prompt_version=None
    )
    artifact = host.store_text(
        "UNIT FIXTURE: synthetic executed evidence; no target code or provider was run"
    )
    evidence = EvidenceRef(
        kind="sandbox_run",
        artifact_id=artifact.id,
        sha256=artifact.sha256,
        commit_sha=ref.commit_sha,
        provenance="fake contract test fixture",
    )
    patch = PatchCandidate(
        id="pat_memory000",
        finding_id=finding.id,
        attempt=1,
        diff_artifact_id=artifact.id,
        diff_sha256=artifact.sha256,
        base_commit_sha=ref.commit_sha,
        worktree_ref="fixture-only",
        files_changed=["app.py", "tests/test_owned.py"],
        tests_added=["tests/test_owned.py"],
        produced_by_run_id=patch_run,
        rationale="unit fixture",
        created_at=utcnow(),
    )
    host.record_patch(patch)
    host.finish_agent_run(verify_run, AgentRunStatus.succeeded)
    verification = VerificationResult(
        id="ver_memory000",
        patch_id=patch.id,
        verdict="accepted",
        checks=[
            VerificationCheck(name=name, passed=True, evidence=[evidence])
            for name in VerificationCheckName
        ],
        sandbox_run_ids=["fixture-only-sandbox"],
        produced_by_run_id=verify_run,
        created_at=utcnow(),
    )
    with pytest.raises(HostError, match="all five"):
        host.record_verification(
            verification.model_copy(update={"checks": verification.checks[:1]})
        )
    host.record_verification(verification)
    assert build_service().verified_regressions(ref) == []  # work is durably queued
    worker.drain(kinds=["register_verified_regression"])
    stored = build_service().verified_regressions(ref)
    assert len(stored) == 1 and stored[0].patch_id == patch.id
    # At-least-once handler replay is safe after the first worker committed.
    context = SimpleNamespace(
        job=SimpleNamespace(
            payload={"assessment_id": assessment_id, "verification_id": verification.id}
        ),
        check_cancelled=lambda: None,
    )
    assert persist_verified_regression(context)["status"] == "candidate_verified"
    assert len(build_service().verified_regressions(ref)) == 1
    packet = alice.post(
        "/api/v1/intelligence/context",
        json={
            "snapshot_ref": ref.model_dump(mode="json"),
            "purpose": "monitoring",
            "focus": [finding.id],
        },
    )
    assert packet.status_code == 200, packet.text
    assert "not proof of merge" in packet.text and verification.id in packet.text
    assert alice.get(f"/api/v1/snapshots/{ref.snapshot_id}/regressions").json()["items"][0][
        "test_paths"
    ] == ["tests/test_owned.py"]
