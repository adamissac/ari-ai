"""Bounded snapshots of regression sources associated with independent verification.

These files are evidence to retain, not a claim that every line/test node ran.
Only platform-selected Verify workspaces may be passed here; never a model URI.
"""

from __future__ import annotations

import hashlib
import stat
from pathlib import Path
from typing import Any

from .sandbox.workspace import recipe_test_roots, resolve_under, safe_rel_path, under_test_roots

MAX_SOURCE_BYTES = 256 * 1024
MAX_TEST_FILES = 32
REQUIRED_CHECKS = {
    "original_check_now_fails_to_reproduce",
    "functional_suite_passes",
    "generated_tests_pass",
    "no_test_tampering",
    "diff_scope_ok",
}


class RegressionEvidenceUnavailable(ValueError):
    pass


def read_sources(root: Path, paths: list[str]) -> dict[str, str]:
    if not paths or len(paths) > MAX_TEST_FILES or len(set(paths)) != len(paths):
        raise RegressionEvidenceUnavailable("no bounded, unique regression source list")
    sources: dict[str, str] = {}
    total = 0
    roots = recipe_test_roots(root)
    for raw in sorted(paths):
        try:
            rel = safe_rel_path(raw)
            if not under_test_roots(rel, roots):
                raise RegressionEvidenceUnavailable(f"regression must be under {list(roots)}")
            target = resolve_under(root, rel)
            current = root
            for part in Path(rel).parts:
                current = current / part
                if current.is_symlink():
                    raise RegressionEvidenceUnavailable("regression sources cannot be symlinks")
            info = target.stat()
            if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_SOURCE_BYTES:
                raise RegressionEvidenceUnavailable("regression source is not a bounded regular file")
            data = target.read_bytes()
            total += len(data)
            if total > MAX_SOURCE_BYTES or not data:
                raise RegressionEvidenceUnavailable("regression source set is empty or too large")
            sources[rel] = data.decode("utf-8")
        except (OSError, UnicodeError) as exc:
            raise RegressionEvidenceUnavailable("regression source cannot be read safely") from exc
    return sources


def verified_bundle(candidate: Any, verification: Any, root: Path, initial: dict[str, str]) -> dict[str, Any]:
    verdict = getattr(verification.verdict, "value", verification.verdict)
    checks = {getattr(c.name, "value", c.name): c.passed for c in verification.checks}
    run = getattr(verification, "verify_run_id", None) or getattr(verification, "produced_by_run_id", None)
    if (
        verdict != "accepted"
        or verification.patch_id != candidate.id
        or not run
        or not verification.sandbox_run_ids
        or not all(checks.get(c) for c in REQUIRED_CHECKS)
    ):
        raise RegressionEvidenceUnavailable("accepted independent verification with all checks required")
    sources = read_sources(root, list(candidate.tests_added))
    if sources != initial:
        raise RegressionEvidenceUnavailable("regression sources changed during verification")
    return {
        "schema_version": "verified-regression-sources.v1",
        "status": "sources_associated_with_accepted_independent_verification",
        "finding_id": candidate.finding_id,
        "patch_id": candidate.id,
        "verification_id": verification.id,
        "verify_run_id": run,
        "sandbox_run_ids": list(verification.sandbox_run_ids),
        "verification_checks": [c.model_dump(mode="json") for c in verification.checks],
        "tests": [
            {
                "path": path,
                "source": source,
                "original_verified_source_sha256": hashlib.sha256(source.encode()).hexdigest(),
            }
            for path, source in sources.items()
        ],
        "limitations": "Accepted Verify outcome associates these sources with executed runs; individual node execution is not claimed. Stored source may be redacted; cite the stored artifact hash.",
    }
