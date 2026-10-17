"""Prefixed, sortable identifiers (docs/12 "Conventions").

IDs look like ``prj_01JABCDEF...`` — a type prefix plus a 26-char Crockford ULID.
Validation accepts any ``<prefix>_[0-9A-Za-z]{8,64}`` body so producers that
derive IDs from content hashes (e.g. RL checkpoints ``ckp_<sha256 prefix>``) or
UUID hex (``rec_<uuid4 hex>``) stay valid; new IDs should use :func:`new_id`.
"""

from __future__ import annotations

import os
import time
from enum import StrEnum
from typing import Annotated

from pydantic import StringConstraints

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


class IdPrefix(StrEnum):
    org = "org"
    usr = "usr"
    prj = "prj"
    rep = "rep"
    snp = "snp"
    sym = "sym"
    ent = "ent"
    exp = "exp"
    scp = "scp"
    apv = "apv"
    asm = "asm"
    run = "run"
    tst = "tst"
    ctx = "ctx"
    fnd = "fnd"
    hyp = "hyp"
    val = "val"
    atp = "atp"
    rc = "rc"
    rmp = "rmp"
    pat = "pat"
    ver = "ver"
    hdn = "hdn"
    aud = "aud"
    evt = "evt"
    rrq = "rrq"
    rec = "rec"
    ckp = "ckp"
    rle = "rle"
    art = "art"
    job = "job"
    dlv = "dlv"
    req = "req"


def ulid() -> str:
    """26-char Crockford base32 ULID: 48-bit ms timestamp + 80 random bits."""
    value = (int(time.time() * 1000) << 80) | int.from_bytes(os.urandom(10), "big")
    out = []
    for _ in range(26):
        out.append(_CROCKFORD[value & 31])
        value >>= 5
    return "".join(reversed(out))


def new_id(prefix: IdPrefix | str) -> str:
    return f"{IdPrefix(prefix).value}_{ulid()}"


def _id_type(prefix: str) -> type[str]:
    return Annotated[  # type: ignore[return-value]
        str, StringConstraints(pattern=rf"^{prefix}_[0-9A-Za-z]{{8,64}}$")
    ]


OrgId = _id_type("org")
UserId = _id_type("usr")
ProjectId = _id_type("prj")
RepositoryId = _id_type("rep")
SnapshotId = _id_type("snp")
SymbolId = _id_type("sym")
EntryPointId = _id_type("ent")
ExpectationId = _id_type("exp")
ScopeId = _id_type("scp")
ApprovalId = _id_type("apv")
AssessmentId = _id_type("asm")
AgentRunId = _id_type("run")
TestRunId = _id_type("tst")
ContextPackId = _id_type("ctx")
FindingId = _id_type("fnd")
HypothesisId = _id_type("hyp")
ValidationId = _id_type("val")
AttackPathId = _id_type("atp")
RootCauseId = _id_type("rc")
RemediationPlanId = _id_type("rmp")
PatchId = _id_type("pat")
VerificationId = _id_type("ver")
HardeningId = _id_type("hdn")
AuditEventId = _id_type("aud")
MonitoringEventId = _id_type("evt")
ReassessmentRequestId = _id_type("rrq")
RecommendationId = _id_type("rec")
CheckpointId = _id_type("ckp")
RLEvaluationId = _id_type("rle")
ArtifactId = _id_type("art")
JobId = _id_type("job")
RequestId = _id_type("req")
