"""Use the host's one durable index for real hosted assessments."""

from __future__ import annotations

import json
from pathlib import PurePosixPath
from typing import Any

from ..contracts import ErrorCode, PlatformError
from ..sandbox.workspace import SnapshotHandle
from .code_intelligence_adapter import CodeIntelligenceAdapter


def shared_host_intel(
    host: Any, snapshot: SnapshotHandle, bindings: list[dict[str, Any]]
) -> CodeIntelligenceAdapter | None:
    factory = getattr(host, "intelligence_service", None)
    if not callable(factory):
        return None  # explicit fake/standalone hosts have no backend store
    if snapshot.pinned_by != "git":
        raise PlatformError(
            ErrorCode.SNAPSHOT_NOT_READY, "Hosted intelligence requires a git-pinned checkout"
        )
    binding = next((b for b in bindings if b.get("repo_id") == host.repo_id), None)
    prefix = str((binding or {}).get("subdir") or "").strip("/")
    if prefix == ".":
        prefix = ""
    recipe = snapshot.root / "build_recipe.json"
    if recipe.is_file():
        target = str(json.loads(recipe.read_text()).get("target_dir") or "")
        if target:
            if PurePosixPath(target).is_absolute() or ".." in PurePosixPath(target).parts:
                raise PlatformError(ErrorCode.SCHEMA_INVALID, "Unsafe target prefix")
            prefix = "/".join(p for p in (prefix, target.strip("/.")) if p)
    service = factory(include_prefix=prefix)
    assessment = host.assessment
    ref = service.index_repository(host.project_id, host.repo_id, assessment.commit_sha)
    host.attach_snapshot(ref)
    adapter = CodeIntelligenceAdapter(service=service, ref=ref, workspace=snapshot.root, path_prefix=prefix)
    adapter.verify_workspace()
    return adapter
