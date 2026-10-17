"""Public backend adapter to the single persistent intelligence service."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

import sqlalchemy as sa

from backend.db import repositories, snapshots, transaction
from backend.intel_store import PostgresPayloadStore
from backend.settings import get_settings
from shared.intelligence import Snapshot, SnapshotRef, SnapshotStatus

if TYPE_CHECKING:
    from code_intelligence.api import IntelligenceService


def build_service() -> IntelligenceService:
    """Queries need only durable stores; ingestion also needs operator bindings."""
    from code_intelligence.api import RepositoryBinding, create_service

    bindings = []
    path = os.environ.get("INTELLIGENCE_REPOSITORIES_FILE")
    if path:
        for item in json.loads(Path(path).read_text()):
            bindings.append(
                RepositoryBinding(
                    project_id=item["project_id"],
                    repo_id=item["repo_id"],
                    full_name=item["full_name"],
                    local_path=Path(item["local_path"]),
                    include_prefix=item.get("include_prefix", ""),
                )
            )
    return create_service(payload_store=PostgresPayloadStore(), repositories=bindings)


def repository_service(
    project_id: str, repo_id: str, *, include_prefix: str = ""
) -> IntelligenceService:
    from code_intelligence.api import RepositoryBinding, create_service

    path = get_settings().repository_bindings_file
    if path is None:
        # Explicit intelligence registration is the alternate operator-owned port.
        service = build_service()
        binding = service.repositories.get(repo_id)
        if binding is None or binding.project_id != project_id:
            raise ValueError("Repository is not registered for canonical intelligence")
        return service
    entries = json.loads(path.read_text())
    entry = next((item for item in entries if item.get("repo_id") == repo_id), None)
    if entry is None:
        raise ValueError("Repository is not registered for canonical intelligence")
    with transaction() as conn:
        name = conn.execute(
            sa.select(repositories.c.full_name).where(
                repositories.c.id == repo_id,
                repositories.c.project_id == project_id,
            )
        ).scalar_one()
    return create_service(
        payload_store=PostgresPayloadStore(),
        repositories=[
            RepositoryBinding(
                project_id=project_id,
                repo_id=repo_id,
                full_name=name,
                local_path=Path(entry["local_path"]).expanduser().resolve(),
                include_prefix=include_prefix or str(entry.get("subdir", "")).strip("/."),
            )
        ],
    )


def snapshot_ref(snapshot_id: str) -> SnapshotRef:
    with transaction() as conn:
        row = conn.execute(
            sa.select(snapshots.c.doc, repositories.c.project_id)
            .join(
                repositories,
                repositories.c.id == snapshots.c.repo_id,
            )
            .where(snapshots.c.id == snapshot_id)
        ).first()
    if row is None:
        raise KeyError("snapshot not found")
    snapshot = Snapshot.model_validate(row.doc)
    if snapshot.status is not SnapshotStatus.ready:
        raise ValueError("SNAPSHOT_NOT_READY: snapshot is not ready")
    return SnapshotRef(
        project_id=row.project_id,
        repo_id=snapshot.repo_id,
        commit_sha=snapshot.commit_sha,
        snapshot_id=snapshot.id,
        index_version=snapshot.index_version,
    )
