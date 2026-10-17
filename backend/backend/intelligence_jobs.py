"""Durable outbox consumer for independent candidate regression evidence."""

from __future__ import annotations

import sqlalchemy as sa

from backend.db import assessments, patch_candidates, transaction, verification_results
from backend.intelligence import build_service, snapshot_ref
from backend.worker import JobContext, PermanentJobError
from shared.assessment import Assessment
from shared.errors import ErrorCode
from shared.findings import PatchCandidate, VerificationResult


def persist_verified_regression(ctx: JobContext) -> dict[str, str]:
    ctx.check_cancelled()
    with transaction() as conn:
        assessment_doc = conn.execute(
            sa.select(assessments.c.doc).where(
                assessments.c.id == ctx.job.payload["assessment_id"],
            )
        ).scalar_one()
        verification_doc = conn.execute(
            sa.select(verification_results.c.doc).where(
                verification_results.c.id == ctx.job.payload["verification_id"],
            )
        ).scalar_one()
        verification = VerificationResult.model_validate(verification_doc)
        patch_doc = conn.execute(
            sa.select(patch_candidates.c.doc).where(
                patch_candidates.c.id == verification.patch_id,
            )
        ).scalar_one()
    assessment = Assessment.model_validate(assessment_doc)
    if not assessment.snapshot_id:
        raise PermanentJobError(
            ErrorCode.SNAPSHOT_NOT_READY, "Regression waits for a canonical assessment snapshot"
        )
    ref = snapshot_ref(assessment.snapshot_id)
    if ref.project_id != assessment.project_id or ref.commit_sha != assessment.commit_sha:
        raise PermanentJobError(ErrorCode.SCHEMA_INVALID, "Regression snapshot mismatch")
    patch = PatchCandidate.model_validate(patch_doc)
    record = build_service().register_verified_regression(ref, patch, verification)
    return {
        "patch_id": record.patch_id,
        "verification_id": record.verification_id,
        "snapshot_id": record.snapshot_ref.snapshot_id,
        "status": "candidate_verified",
    }
