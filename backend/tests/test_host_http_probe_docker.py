from __future__ import annotations

import json
import os

import pytest
from sqlalchemy import select

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_DOCKER_SANDBOX") != "1",
    reason="needs RUN_DOCKER_SANDBOX=1 and SANDBOX_IMAGE",
)

pytest.importorskip("security_agents")


def test_hosted_http_probe_evidence_is_persisted(
    client_factory, settings_override, monkeypatch, tmp_path
):
    from test_security_agents_host_mode import test_host_mode_full_flow_against_real_backend

    from backend.artifacts import ArtifactStore
    from backend.db import finding_records, transaction

    monkeypatch.setenv("SECURITY_AGENTS_PROBE_TRANSPORT", "http")

    def docker_settings(**values: str) -> None:
        settings_override(**{**values, "security_sandbox": "docker"})

    test_host_mode_full_flow_against_real_backend(
        client_factory, docker_settings, monkeypatch, tmp_path
    )

    with transaction() as conn:
        docs = (
            conn.execute(
                select(finding_records.c.doc).where(
                    finding_records.c.record_type == "validation_result"
                )
            )
            .scalars()
            .all()
        )
        assert docs, "no persisted validation record"
        refs = [e for doc in docs for e in doc["evidence"] if e["kind"] == "tool_output"]
        assert refs, f"validation record cites no http evidence artifact: {docs}"
        meta, data = ArtifactStore().get(conn, refs[-1]["artifact_id"])
    assert meta["sha256"] == refs[-1]["sha256"]
    evidence = json.loads(data)
    assert evidence["transport"] == "http" and evidence["target_contacted"] is True
    assert evidence["driver"] == "docker" and evidence["network"] == "target-only"
    reads = [r for r in evidence["target_requests"] if r["path"].startswith("/payments/")]
    assert len(reads) == 2 and all(r["status"] == 200 for r in reads), evidence["target_requests"]
