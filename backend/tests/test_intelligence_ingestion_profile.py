"""Real PostgreSQL scope identity; owned fixture source is indexed, never executed."""

from __future__ import annotations

from dataclasses import replace

from helpers import setup_project
from test_payload_store_intel_integration import two_commits as two_commits

from backend.intel_store import PostgresPayloadStore
from code_intelligence.api import RepositoryBinding, create_service
from shared.intelligence_memory import ExpectationDecisionRequest


def test_postgres_profiles_remain_distinct_and_readable_after_restart(
    client_factory,
    two_commits,
) -> None:  # type: ignore[no-untyped-def]
    alice, bob = client_factory("profile-alice"), client_factory("profile-bob")
    ids = setup_project(alice, bob)
    root, _, head, _ = two_commits
    binding = RepositoryBinding(ids["project"], ids["repo"], "acme/payments-lite", root)
    full = create_service(payload_store=PostgresPayloadStore(), repositories=[binding])
    full_ref = full.index_repository(ids["project"], ids["repo"], head)
    before = full.store.get(full_ref).model_dump_json()
    expectation = full.expectations(full_ref)[0]
    full.decide_expectation(
        full_ref,
        expectation.id,
        ExpectationDecisionRequest(
            status="confirmed",
            reason="Fixture decision belongs to original coverage",
            expected_revision=0,
        ),
        actor_id=alice.me["user"]["id"],
    )

    restricted_binding = replace(binding, include_prefix="payments_lite")
    narrow = create_service(payload_store=PostgresPayloadStore(), repositories=[restricted_binding])
    narrow_ref = narrow.index_repository(ids["project"], ids["repo"], head)
    assert narrow_ref != full_ref
    assert len(narrow_ref.index_version) <= 80
    assert all(s.path.startswith("payments_lite/") for s in narrow.symbols(narrow_ref))
    assert len(narrow.symbols(narrow_ref)) < len(full.symbols(full_ref))
    assert narrow.memory is not None and narrow.memory.decisions(narrow_ref) == []
    assert full.store.get(full_ref).model_dump_json() == before

    restarted = create_service(
        payload_store=PostgresPayloadStore(), repositories=[restricted_binding]
    )
    assert restarted.index_repository(ids["project"], ids["repo"], head) == narrow_ref
    for ref in (full_ref, narrow_ref):
        response = alice.get(f"/api/v1/snapshots/{ref.snapshot_id}")
        assert response.status_code == 200
        assert response.json()["index_version"] == ref.index_version
        assert response.json()["status"] == "ready"
        assert (
            PostgresPayloadStore().find_snapshot(
                ref.project_id, ref.repo_id, head, ref.index_version
            )
            == ref
        )
