"""Auto delivery (ADR-0020): pre-approved remediation and push of Verify-accepted patches.

In ``review`` mode (the default) nothing here acts: a human approves each remediation and
no code reaches the repository. In ``auto`` mode the owner who switched it on is the
recorded approver of every remediation approval of that project, and a patch whose
independent Verify verdict is ``accepted`` is committed onto the repository's default
branch. Nothing else is pushed: a rejected, inconclusive or unverified patch never leaves
the sandbox, and a patch that no longer applies to the branch tip is reported, not forced.
"""

from __future__ import annotations

import base64
import re
import tempfile
from pathlib import Path
from typing import Any

import sqlalchemy as sa

from backend import audit, jobs
from backend.artifacts import ArtifactStore
from backend.checkouts import FULL_NAME_RE, CheckoutError, _git, _locked, fetch_commit
from backend.db import (
    approvals,
    assessments,
    patch_candidates,
    repositories,
    transaction,
    verification_results,
)
from backend.services import project_org, project_settings
from backend.settings import get_settings
from backend.worker import JobContext, PermanentJobError, handler
from shared.audit import ActorType
from shared.base import utcnow
from shared.errors import ErrorCode
from shared.findings import PatchCandidate, VerificationResult
from shared.scope import Approval, ApprovalStatus, ApprovalSubject
from shared.tenancy import DeliveryMode

BRANCH_RE = r"^[A-Za-z0-9._/\-]+$"
COMMIT_AUTHOR = ("Ari", "ari@users.noreply.github.com")


def auto_approver(conn: Any, project_id: str) -> str | None:
    """The owner who authorized auto delivery, or None in review mode."""
    s = project_settings(conn, project_id)
    if s.delivery_mode is DeliveryMode.auto and s.auto_delivery_enabled_by:
        return s.auto_delivery_enabled_by
    return None


def auto_approve_pending(assessment_id: str, project_id: str) -> list[str]:
    """Approve this assessment's pending remediation approvals on the authorizing owner's
    behalf and enqueue the resume. Returns the approval ids (empty in review mode)."""
    with transaction() as conn:
        approver = auto_approver(conn, project_id)
        if approver is None:
            return []
        rows = conn.execute(
            sa.select(approvals.c.id, approvals.c.doc)
            .where(
                approvals.c.assessment_id == assessment_id,
                approvals.c.subject_type == ApprovalSubject.remediation.value,
                approvals.c.status == ApprovalStatus.pending.value,
            )
            .order_by(approvals.c.created_at)
            .with_for_update()
        ).all()
        ids = []
        org_id = project_org(conn, project_id)
        for row in rows:
            ap = Approval.model_validate(row.doc).model_copy(
                update={
                    "status": ApprovalStatus.approved,
                    "decided_by": approver,
                    "decided_at": utcnow(),
                    "reason": "auto delivery: pre-approved by the project owner",
                }
            )
            conn.execute(
                sa.update(approvals)
                .where(approvals.c.id == ap.id)
                .values(status=ap.status.value, doc=ap.model_dump(mode="json"))
            )
            audit.record(
                conn,
                org_id=org_id,
                project_id=project_id,
                actor_type=ActorType.system,
                actor_id="auto-delivery",
                action="approval.auto_approved",
                subject_type="approval",
                subject_id=ap.id,
                details={"on_behalf_of": approver, "subject_id": ap.subject_id},
            )
            ids.append(ap.id)
        if ids:
            jobs.enqueue(
                conn,
                "run_assessment",
                {"assessment_id": assessment_id},
                dedupe_key=f"asm:{assessment_id}:resume:auto:{ids[-1]}",
            )
        return ids


def push_patch(
    repo_dir: Path,
    full_name: str,
    branch: str,
    diff: bytes,
    token: str,
    message: str,
    *,
    github_web_url: str = "https://github.com",
) -> str:
    """Apply ``diff`` onto the current tip of ``branch`` and push it (never forced).

    Returns the new commit SHA. Raises CheckoutError when the patch does not apply or the
    branch moved during the push."""
    if not FULL_NAME_RE.match(full_name):
        raise CheckoutError(f"invalid repository name {full_name!r}")
    if not re.match(BRANCH_RE, branch) or ".." in branch:
        raise CheckoutError(f"invalid branch name {branch!r}")
    url = f"{github_web_url.rstrip('/')}/{full_name}.git"
    auth = base64.b64encode(f"x-access-token:{token}".encode()).decode()
    header = f"http.extraHeader=Authorization: Basic {auth}"
    tip_ref = "refs/ari/delivery-tip"
    _git(
        "-C", str(repo_dir), "-c", header, "fetch", "--quiet", "--depth=1", "--no-tags",
        url, f"+refs/heads/{branch}:{tip_ref}",
    )  # fmt: skip
    with tempfile.TemporaryDirectory(prefix="ari-delivery-") as tmp:
        wt = Path(tmp) / "wt"
        patch_file = Path(tmp) / "fix.diff"
        patch_file.write_bytes(diff)
        _git("-C", str(repo_dir), "worktree", "add", "--quiet", "--detach", str(wt), tip_ref)
        try:
            try:
                _git("-C", str(wt), "apply", "--index", str(patch_file))
            except CheckoutError as exc:
                raise CheckoutError(f"patch no longer applies to {branch}: {exc}") from exc
            name, email = COMMIT_AUTHOR
            _git(
                "-C", str(wt), "-c", f"user.name={name}", "-c", f"user.email={email}",
                "commit", "--quiet", "--no-verify", "-m", message,
            )  # fmt: skip
            sha = _git("-C", str(wt), "rev-parse", "HEAD").strip()
            _git("-C", str(wt), "-c", header, "push", "--quiet", url, f"HEAD:refs/heads/{branch}")
        finally:
            _git("-C", str(repo_dir), "worktree", "remove", "--force", str(wt))
    return sha


def _record(conn: Any, org_id: str, project_id: str, action: str, details: dict[str, Any]) -> None:
    audit.record(
        conn,
        org_id=org_id,
        project_id=project_id,
        actor_type=ActorType.system,
        actor_id="auto-delivery",
        action=action,
        subject_type="patch",
        subject_id=str(details["patch_id"]),
        details=details,
    )


@handler("deliver_verified_patch")
def deliver_verified_patch(ctx: JobContext) -> dict[str, Any]:
    ctx.check_cancelled()
    s = get_settings()
    with transaction() as conn:
        vdoc = conn.execute(
            sa.select(verification_results.c.doc).where(
                verification_results.c.id == ctx.job.payload["verification_id"]
            )
        ).scalar_one()
        verification = VerificationResult.model_validate(vdoc)
        if verification.verdict.value != "accepted":
            raise PermanentJobError(ErrorCode.FORBIDDEN, "only Verify-accepted patches are pushed")
        patch = PatchCandidate.model_validate(
            conn.execute(
                sa.select(patch_candidates.c.doc).where(
                    patch_candidates.c.id == verification.patch_id
                )
            ).scalar_one()
        )
        asm = (
            conn.execute(
                sa.select(assessments.c.project_id, assessments.c.repo_id).where(
                    assessments.c.id == ctx.job.payload["assessment_id"]
                )
            )
            .mappings()
            .one()
        )
        project_id = asm["project_id"]
        org_id = project_org(conn, project_id)
        details: dict[str, Any] = {
            "patch_id": patch.id,
            "verification_id": verification.id,
            "finding_id": patch.finding_id,
        }
        if auto_approver(conn, project_id) is None:
            _record(conn, org_id, project_id, "delivery.skipped", details)
            return {"status": "skipped", "reason": "delivery mode is review"}
        repo = (
            conn.execute(sa.select(repositories).where(repositories.c.id == asm["repo_id"]))
            .mappings()
            .first()
        )
        connected = repo is not None and repo["installation_id"] is not None
        if connected:
            _, diff = ArtifactStore().get(conn, patch.diff_artifact_id)
    if not connected:
        with transaction() as conn:  # own transaction: the raise below must not roll it back
            _record(conn, org_id, project_id, "delivery.failed", details | {"reason": "no app"})
        raise PermanentJobError(
            ErrorCode.SUBSYSTEM_UNAVAILABLE, "repository is not connected through the GitHub App"
        )
    assert repo is not None
    if s.security_workdir is None:
        raise PermanentJobError(ErrorCode.SUBSYSTEM_UNAVAILABLE, "SECURITY_WORKDIR is not set")
    from backend.github import GitHubApp

    token = GitHubApp(settings=s).installation_token(int(repo["installation_id"]), write=True)
    repo_dir = s.security_workdir / "repos" / f"{repo['id']}.git"
    message = (
        f"fix: {patch.rationale}\n\n"
        f"Applied by Ari auto delivery. Finding {patch.finding_id}, patch {patch.id},\n"
        f"independently verified by {verification.id}."
    )
    try:
        with _locked(repo_dir):
            fetch_commit(
                repo_dir,
                str(repo["full_name"]),
                patch.base_commit_sha,
                token,
                github_web_url=s.github_web_url,
            )
            sha = push_patch(
                repo_dir,
                str(repo["full_name"]),
                str(repo["default_branch"]),
                diff,
                token,
                message,
                github_web_url=s.github_web_url,
            )
    except CheckoutError as exc:
        with transaction() as conn:
            _record(conn, org_id, project_id, "delivery.failed", details | {"reason": str(exc)})
        raise PermanentJobError(ErrorCode.CONFLICT_STATE, str(exc)) from exc
    with transaction() as conn:
        _record(
            conn,
            org_id,
            project_id,
            "delivery.pushed",
            details | {"commit_sha": sha, "branch": repo["default_branch"]},
        )
    return {"status": "pushed", "commit_sha": sha, "branch": repo["default_branch"]}
