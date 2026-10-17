from __future__ import annotations

import pytest
from pydantic import ValidationError

from shared.base import utcnow
from shared.evidence import EvidenceKind, EvidenceRef
from shared.intelligence import SnapshotRef
from shared.intelligence_memory import (
    ExpectationDecision,
    ExpectationDecisionRequest,
    VerifiedRegression,
)


def ref() -> SnapshotRef:
    return SnapshotRef(
        project_id="prj_12345678",
        repo_id="rep_12345678",
        snapshot_id="snp_12345678",
        commit_sha="a" * 40,
        index_version="test/1",
    )


def test_decisions_do_not_accept_model_actor_or_unresolved_status() -> None:
    value = dict(status="confirmed", reason="Confirmed business rule", expected_revision=0)
    assert ExpectationDecisionRequest(**value).status == "confirmed"
    for changes in (
        {"status": "inferred"},
        {"decided_by": "usr_12345678"},
        {"expected_revision": -1},
        {"reason": "  "},
        {"reason": "sk-ant-testcredential123456"},
    ):
        with pytest.raises(ValidationError):
            ExpectationDecisionRequest.model_validate({**value, **changes})
    decision = ExpectationDecision(
        **value,
        snapshot_ref=ref(),
        expectation_id="exp_12345678",
        revision=1,
        decided_by="usr_12345678",
        decided_at=utcnow(),
    )
    assert ExpectationDecision.model_validate_json(decision.model_dump_json()) == decision


def test_candidate_regression_rejects_unsafe_paths_and_keeps_base_commit() -> None:
    value = dict(
        snapshot_ref=ref(),
        finding_id="fnd_12345678",
        patch_id="pat_12345678",
        verification_id="ver_12345678",
        test_paths=["tests/test_owned.py"],
        evidence=[
            EvidenceRef(
                kind=EvidenceKind.test_run,
                artifact_id="art_12345678",
                sha256="b" * 64,
                provenance="contract fixture",
            )
        ],
        created_at=utcnow(),
    )
    record = VerifiedRegression(**value)
    assert record.snapshot_ref.commit_sha == "a" * 40
    for paths in ([], ["../escape.py"], ["/tmp/test.py"], ["x.py", "x.py"]):
        with pytest.raises(ValidationError):
            VerifiedRegression.model_validate({**value, "test_paths": paths})
