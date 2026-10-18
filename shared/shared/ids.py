"""Prefixed, sortable identifiers (docs/12 "Conventions").

IDs look like ``prj_01JABCDEF...`` — a type prefix plus a 26-char Crockford ULID.
Validation accepts any ``<prefix>_[0-9A-Za-z_-]{8,64}`` body (0.4.0: ``_``/``-`` allowed for
readable producer ids such as ``exp_tenant_isolation_payments``) so producers that
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
    itk = "itk"
    rtw = "rtw"
    inc = "inc"
    lap = "lap"  # live-defense connected application
    lgr = "lgr"  # live-defense action grant
    sev = "sev"  # security telemetry event
    lin = "lin"  # live incident
    dac = "dac"  # defense action
    lnt = "lnt"  # live notification


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


def _pattern(prefix: str) -> StringConstraints:
    return StringConstraints(pattern=rf"^{prefix}_[0-9A-Za-z_\-]{{8,64}}$")


OrgId = Annotated[str, _pattern("org")]
UserId = Annotated[str, _pattern("usr")]
ProjectId = Annotated[str, _pattern("prj")]
RepositoryId = Annotated[str, _pattern("rep")]
SnapshotId = Annotated[str, _pattern("snp")]
SymbolId = Annotated[str, _pattern("sym")]
EntryPointId = Annotated[str, _pattern("ent")]
ExpectationId = Annotated[str, _pattern("exp")]
ScopeId = Annotated[str, _pattern("scp")]
ApprovalId = Annotated[str, _pattern("apv")]
AssessmentId = Annotated[str, _pattern("asm")]
AgentRunId = Annotated[str, _pattern("run")]
TestRunId = Annotated[str, _pattern("tst")]
ContextPackId = Annotated[str, _pattern("ctx")]
FindingId = Annotated[str, _pattern("fnd")]
HypothesisId = Annotated[str, _pattern("hyp")]
ValidationId = Annotated[str, _pattern("val")]
AttackPathId = Annotated[str, _pattern("atp")]
RootCauseId = Annotated[str, _pattern("rc")]
RemediationPlanId = Annotated[str, _pattern("rmp")]
PatchId = Annotated[str, _pattern("pat")]
VerificationId = Annotated[str, _pattern("ver")]
HardeningId = Annotated[str, _pattern("hdn")]
AuditEventId = Annotated[str, _pattern("aud")]
MonitoringEventId = Annotated[str, _pattern("evt")]
ReassessmentRequestId = Annotated[str, _pattern("rrq")]
RecommendationId = Annotated[str, _pattern("rec")]
CheckpointId = Annotated[str, _pattern("ckp")]
RLEvaluationId = Annotated[str, _pattern("rle")]
ArtifactId = Annotated[str, _pattern("art")]
JobId = Annotated[str, _pattern("job")]
RequestId = Annotated[str, _pattern("req")]
IngestTokenId = Annotated[str, _pattern("itk")]
IncidentId = Annotated[str, _pattern("inc")]
LiveAppId = Annotated[str, _pattern("lap")]
LiveGrantId = Annotated[str, _pattern("lgr")]
SecurityEventId = Annotated[str, _pattern("sev")]
LiveIncidentId = Annotated[str, _pattern("lin")]
DefenseActionId = Annotated[str, _pattern("dac")]
LiveNotificationId = Annotated[str, _pattern("lnt")]
