"""Trusted repository binding to SHA-pinned workspace and upstream intelligence."""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

from ..contracts import ErrorCode, PlatformError, new_id
from ..sandbox.workspace import SnapshotHandle, copy_tree, resolve_under, safe_rel_path
from .code_intelligence_adapter import CodeIntelligenceAdapter


def bindings_path() -> Path | None:
    try:
        from backend.settings import get_settings
        configured = get_settings().repository_bindings_file
    except ImportError:
        configured = None
    raw = configured or os.environ.get("REPOSITORY_BINDINGS_FILE")
    return Path(raw) if raw else None


def bound_intelligence(host: Any, workdir: Path, service: Any = None) -> CodeIntelligenceAdapter:
    """Read target bytes from git, never from the mutable working tree.

    REPOSITORY_BINDINGS_FILE is trusted operator configuration with the backend's
    existing list shape: repo_id, local_path, subdir. Intelligence owns indexing.
    """
    path = bindings_path()
    if path is None:
        raise PlatformError(ErrorCode.SNAPSHOT_NOT_READY, "REPOSITORY_BINDINGS_FILE is required")
    bindings = json.loads(path.read_text())
    matches = [binding for binding in bindings if binding.get("repo_id") == host.repo_id]
    if len(matches) != 1:
        raise PlatformError(ErrorCode.SNAPSHOT_NOT_READY, "repository needs exactly one trusted binding")
    binding = matches[0]
    subdir = binding.get("subdir", ".")
    subdir = "." if subdir == "." else safe_rel_path(subdir)
    assessment = host.assessment
    raw = SnapshotHandle.from_git(
        Path(binding["local_path"]).expanduser().resolve(), assessment.commit_sha, subdir,
        workdir / "checkout", snapshot_id=getattr(assessment, "snapshot_id", None) or new_id("snp"),
        repo_id=host.repo_id,
    )
    recipe = raw.root / "build_recipe.json"
    target_dir = json.loads(recipe.read_text()).get("target_dir") if recipe.is_file() else None
    workspace = raw.root
    prefix_parts = [] if subdir == "." else [subdir]
    if target_dir:
        target_dir = safe_rel_path(target_dir)
        source = resolve_under(raw.root, target_dir)
        workspace = workdir / "snapshot"
        copy_tree(source, workspace)
        shutil.copy2(recipe, workspace / "build_recipe.json")
        prefix_parts.append(target_dir)
    if service is None:
        from code_intelligence.api import build_service
        service = build_service()
    ref = service.index_repository(host.project_id, host.repo_id, assessment.commit_sha)
    if ref.commit_sha != raw.commit_sha or ref.repo_id != host.repo_id or ref.project_id != host.project_id:
        raise PlatformError(ErrorCode.SNAPSHOT_NOT_READY, "intelligence snapshot identity mismatch")
    adapter = CodeIntelligenceAdapter(
        service=service, ref=ref, workspace=workspace, path_prefix="/".join(prefix_parts),
    )
    adapter.verify_workspace()
    return adapter
