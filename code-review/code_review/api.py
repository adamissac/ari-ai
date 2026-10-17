"""Public API of the reviewer (consumed by the orchestrator / worker).

    review(host, ReviewRequest) -> ReviewResult                       (shared contract)
    review_full(host, ReviewRequest) -> ReviewOutcome                 (+ test sources, handoffs)
    generate_tests(host, ReviewRequest, statements) -> list[GeneratedTest]
    propose_repair(host, finding_id, approval_id) -> RepairOutcome    (approval-gated)
    review_assessment(host) -> ReviewOutcome                          (FUNCTIONAL_REVIEW entry)

Repositories are registered explicitly by the operator (never cloned from model input):
``CODE_REVIEW_REPOSITORIES="rep_<id>=/abs/path/to/repo#optional/subdir;..."``.
Code intelligence is used when ``code_intelligence.api:build_service`` is importable;
otherwise the reviewer says it is unavailable and works from the pinned files.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any

from code_review.agent import BUNDLE_KIND, ReviewerAgentRunner, ReviewError
from code_review.models import GeneratedTestSource, RepairOutcome, ReviewOutcome
from code_review.ports import IntelligencePort, RepoSource, ReviewHost, SandboxPort
from code_review.tools import ReviewBudget
from shared.assessment import AssessmentTrigger
from shared.errors import ErrorCode
from shared.evidence import EvidenceKind
from shared.findings import Finding
from shared.intelligence import SnapshotRef
from shared.review import (
    ChangeIntent,
    ChangeIntentSource,
    GeneratedTest,
    ReviewRequest,
    ReviewResult,
)


def _bindings_file_entries() -> list[dict[str, Any]]:
    """The backend's shared registry (``REPOSITORY_BINDINGS_FILE``), if configured."""
    try:
        from backend.settings import get_settings

        path = get_settings().repository_bindings_file
    except Exception:
        return []
    if not path or not Path(path).exists():
        return []
    return list(json.loads(Path(path).read_text()))


def _recipe_target_dir(local: Path, subdir: str, commit_sha: str) -> str | None:
    """``build_recipe.json`` ``target_dir`` read from git at exactly ``commit_sha``."""
    spec = f"{commit_sha}:{subdir + '/' if subdir else ''}build_recipe.json"
    proc = subprocess.run(
        ["git", "-C", str(local), "show", spec], capture_output=True, timeout=30, check=False
    )
    if proc.returncode != 0:
        return None
    target = json.loads(proc.stdout or b"{}").get("target_dir")
    if not target:
        return None
    if target.startswith("/") or ".." in Path(target).parts:
        raise ReviewError(
            ErrorCode.VALIDATION_FAILED, "build_recipe.json target_dir must be relative"
        )
    return str(target).strip("/")


def resolve_repo(
    repo_id: str, registry: str | None = None, *, commit_sha: str | None = None
) -> RepoSource:
    """Find the operator-registered checkout for ``repo_id``.

    Sources, in order: ``CODE_REVIEW_REPOSITORIES`` (``rep_x=/abs/path#subdir;...``), then the
    backend's ``REPOSITORY_BINDINGS_FILE`` (JSON ``[{repo_id, local_path, subdir}]``), so the
    reviewer and the security runtime use one registry. A ``build_recipe.json`` with
    ``target_dir`` at the reviewed commit narrows the project root, as the security adapter does.
    """
    raw = registry if registry is not None else os.environ.get("CODE_REVIEW_REPOSITORIES", "")
    found: tuple[Path, str] | None = None
    for item in filter(None, (p.strip() for p in raw.split(";"))):
        rid, _, rest = item.partition("=")
        if rid.strip() == repo_id:
            path, _, subdir = rest.partition("#")
            found = (Path(path.strip()), subdir)
            break
    if found is None and registry is None:
        for entry in _bindings_file_entries():
            if entry.get("repo_id") == repo_id:
                found = (Path(entry["local_path"]).expanduser().resolve(), entry.get("subdir", ""))
                break
    if found is None:
        raise ReviewError(
            ErrorCode.SUBSYSTEM_UNAVAILABLE, f"repository {repo_id} is not registered for review"
        )
    local, subdir = found
    subdir = subdir.strip().strip("/")
    subdir = "" if subdir in ("", ".") else subdir
    if not local.is_absolute() or not (local / ".git").exists():
        raise ReviewError(ErrorCode.SUBSYSTEM_UNAVAILABLE, f"{repo_id} is not a local git repo")
    if commit_sha:
        target = _recipe_target_dir(local, subdir, commit_sha)
        if target:
            subdir = f"{subdir}/{target}" if subdir else target
    return RepoSource(local_path=local, subdir=subdir)


def build_intelligence() -> IntelligencePort | None:
    try:
        from code_intelligence.api import build_service  # type: ignore[import-not-found]
    except ImportError:
        return None
    try:
        return build_service()  # type: ignore[no-any-return]
    except Exception:
        return None


def _runner(
    host: ReviewHost,
    repo_id: str,
    *,
    commit_sha: str | None = None,
    source: RepoSource | None,
    sandbox: SandboxPort | None,
    intelligence: IntelligencePort | None | bool,
    budget: ReviewBudget | None,
) -> ReviewerAgentRunner:
    kw: dict[str, Any] = {
        "host": host,
        "source": source or resolve_repo(repo_id, commit_sha=commit_sha),
        "intelligence": build_intelligence() if intelligence is True else (intelligence or None),
        "budget": budget or ReviewBudget(),
    }
    if sandbox is not None:
        kw["sandbox"] = sandbox
    return ReviewerAgentRunner(**kw)


def review_full(
    host: ReviewHost,
    request: ReviewRequest,
    *,
    source: RepoSource | None = None,
    sandbox: SandboxPort | None = None,
    intelligence: IntelligencePort | None | bool = True,
    budget: ReviewBudget | None = None,
    focus_statements: list[str] | None = None,
) -> ReviewOutcome:
    runner = _runner(
        host,
        request.snapshot_ref.repo_id,
        commit_sha=request.change_intent.head_sha,
        source=source,
        sandbox=sandbox,
        intelligence=intelligence,
        budget=budget,
    )
    return runner.review(request, focus_statements=focus_statements)


def review(host: ReviewHost, request: ReviewRequest, **kw: Any) -> ReviewResult:
    return review_full(host, request, **kw).result


def generate_tests(
    host: ReviewHost, request: ReviewRequest, statements: list[str], **kw: Any
) -> list[GeneratedTest]:
    """Behavioral tests for given expectation statements (also used by Fortify)."""
    if not statements:
        raise ReviewError(
            ErrorCode.VALIDATION_FAILED, "generate_tests needs at least one statement"
        )
    return review_full(host, request, focus_statements=statements, **kw).generated_tests


def read_artifact(host: ReviewHost, artifact_id: str) -> bytes:
    reader = getattr(host, "read_artifact", None)
    if callable(reader):
        return reader(artifact_id)  # type: ignore[no-any-return]
    from backend.db import transaction

    with transaction() as conn:
        _, data = host.store.get(conn, artifact_id)  # type: ignore[attr-defined]
    return data


def load_test_sources(host: ReviewHost, finding: Finding) -> list[GeneratedTestSource]:
    """Recover the validated finding's generated tests from its cited bundle artifact."""
    out: list[GeneratedTestSource] = []
    for ev in finding.evidence:
        if ev.kind is not EvidenceKind.artifact or not (ev.note or "").startswith(BUNDLE_KIND):
            continue
        data = read_artifact(host, ev.artifact_id or "")
        if hashlib.sha256(data).hexdigest() != ev.sha256:
            raise ReviewError(ErrorCode.VALIDATION_FAILED, "test bundle artifact hash mismatch")
        for t in json.loads(data)["tests"]:
            if "content_b64" in t:
                t["content"] = base64.b64decode(t.pop("content_b64")).decode()
            if hashlib.sha256(t["content"].encode()).hexdigest() != t["sha256"]:
                raise ReviewError(
                    ErrorCode.VALIDATION_FAILED, "generated test content hash mismatch"
                )
            out.append(GeneratedTestSource(**t))
    return out


def propose_repair(
    host: ReviewHost,
    finding_id: str,
    approval_id: str,
    *,
    repo_id: str,
    source: RepoSource | None = None,
    sandbox: SandboxPort | None = None,
    budget: ReviewBudget | None = None,
    attempt: int = 1,
) -> RepairOutcome:
    finding = next((f for f in host.findings() if f.id == finding_id), None)  # type: ignore[attr-defined]
    approval = next((a for a in host.approvals() if a.id == approval_id), None)
    if finding is None or approval is None:
        raise ReviewError(ErrorCode.NOT_FOUND, "finding or approval not found in this assessment")
    runner = _runner(
        host,
        repo_id,
        commit_sha=finding.commit_sha,
        source=source,
        sandbox=sandbox,
        intelligence=False,
        budget=budget,
    )
    return runner.repair(finding, approval, load_test_sources(host, finding), attempt=attempt)


def _snapshot_for(repo_id: str, commit_sha: str, snapshot_id: str | None) -> tuple[str, str]:
    """(snapshot_id, index_version) of the backend snapshot row for this exact commit."""
    import sqlalchemy as sa

    from backend.db import snapshots, transaction

    q = sa.select(snapshots.c.id, snapshots.c.index_version, snapshots.c.status).where(
        snapshots.c.repo_id == repo_id, snapshots.c.commit_sha == commit_sha
    )
    if snapshot_id:
        q = q.where(snapshots.c.id == snapshot_id)
    with transaction() as conn:
        rows = conn.execute(q.order_by(snapshots.c.created_at.desc())).mappings().all()
    ready = [r for r in rows if r["status"] == "ready"] or rows
    if not ready:
        raise ReviewError(
            ErrorCode.SNAPSHOT_NOT_READY, f"no snapshot recorded for {repo_id}@{commit_sha[:12]}"
        )
    return ready[0]["id"], ready[0]["index_version"]


def review_assessment(
    host: ReviewHost,
    *,
    change_intent: ChangeIntent | None = None,
    focus_paths: list[str] | None = None,
    **kw: Any,
) -> ReviewOutcome:
    """One-call entry for the orchestrator's FUNCTIONAL_REVIEW step.

    Builds the ``ReviewRequest`` from the assessment (exact commit, its recorded snapshot,
    budget). Without an explicit ``change_intent`` (e.g. a manual assessment) it is a
    full-snapshot review of ``assessment.commit_sha``; monitoring callers should pass the
    push/PR intent (title, body, base_sha) so the diff is reviewed against its intent.
    """
    a = host.assessment  # type: ignore[attr-defined]
    repo_id: str = host.repo_id  # type: ignore[attr-defined]
    snapshot_id, index_version = _snapshot_for(repo_id, a.commit_sha, a.snapshot_id)
    intent = change_intent or ChangeIntent(
        source=ChangeIntentSource.push
        if a.trigger is AssessmentTrigger.monitoring
        else ChangeIntentSource.manual,
        title=f"{a.trigger.value} assessment of {a.commit_sha[:12]}",
        head_sha=a.commit_sha,
    )
    if intent.head_sha != a.commit_sha:
        raise ReviewError(
            ErrorCode.VALIDATION_FAILED, "change intent head_sha != assessment commit"
        )
    request = ReviewRequest(
        assessment_id=a.id,
        snapshot_ref=SnapshotRef(
            project_id=a.project_id,
            repo_id=repo_id,
            commit_sha=a.commit_sha,
            snapshot_id=snapshot_id,
            index_version=index_version,
        ),
        change_intent=intent,
        focus_paths=focus_paths or [],
        budget=a.budget,
    )
    return review_full(host, request, **kw)
