"""Public API of the reviewer (consumed by the orchestrator / worker).

    review(host, ReviewRequest) -> ReviewResult                       (shared contract)
    review_full(host, ReviewRequest) -> ReviewOutcome                 (+ test sources, handoffs)
    generate_tests(host, ReviewRequest, statements) -> list[GeneratedTest]
    propose_repair(host, finding_id, approval_id) -> RepairOutcome    (approval-gated)

Repositories are registered explicitly by the operator (never cloned from model input):
``CODE_REVIEW_REPOSITORIES="rep_<id>=/abs/path/to/repo#optional/subdir;..."``.
Code intelligence is used when ``code_intelligence.api:build_service`` is importable;
otherwise the reviewer says it is unavailable and works from the pinned files.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from code_review.agent import BUNDLE_KIND, ReviewerAgentRunner, ReviewError
from code_review.models import GeneratedTestSource, RepairOutcome, ReviewOutcome
from code_review.ports import IntelligencePort, RepoSource, ReviewHost, SandboxPort
from code_review.tools import ReviewBudget
from shared.errors import ErrorCode
from shared.evidence import EvidenceKind
from shared.findings import Finding
from shared.review import GeneratedTest, ReviewRequest, ReviewResult


def resolve_repo(repo_id: str, registry: str | None = None) -> RepoSource:
    raw = registry if registry is not None else os.environ.get("CODE_REVIEW_REPOSITORIES", "")
    for item in filter(None, (p.strip() for p in raw.split(";"))):
        rid, _, rest = item.partition("=")
        if rid.strip() != repo_id:
            continue
        path, _, subdir = rest.partition("#")
        local = Path(path.strip())
        if not local.is_absolute() or not (local / ".git").exists():
            raise ReviewError(ErrorCode.SUBSYSTEM_UNAVAILABLE, f"{repo_id} is not a local git repo")
        return RepoSource(local_path=local, subdir=subdir.strip().strip("/"))
    raise ReviewError(
        ErrorCode.SUBSYSTEM_UNAVAILABLE, f"repository {repo_id} is not registered for review"
    )


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
    source: RepoSource | None,
    sandbox: SandboxPort | None,
    intelligence: IntelligencePort | None | bool,
    budget: ReviewBudget | None,
) -> ReviewerAgentRunner:
    kw: dict[str, Any] = {
        "host": host,
        "source": source or resolve_repo(repo_id),
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
        host, repo_id, source=source, sandbox=sandbox, intelligence=False, budget=budget
    )
    return runner.repair(finding, approval, load_test_sources(host, finding), attempt=attempt)
