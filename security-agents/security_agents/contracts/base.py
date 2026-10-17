"""Base types for the local V0 contract adapter.

STATUS: LOCAL ADAPTER, NOT CANONICAL. The canonical schemas belong to `shared/`
(owner: Srihith, CORE-001). Until that package lands, `security_agents` builds
against these typed models, which mirror docs/12_DATA_MODELS_AND_CONTRACTS.md
field-for-field. When `shared/` merges, this package becomes a thin re-export /
adapter layer and the contract tests in `tests/test_contracts.py` must keep
passing against it.
"""

from __future__ import annotations

import os
import time
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

SCHEMA_VERSION = "0.1.0-local"

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def _ulid() -> str:
    """Return a 26-char Crockford base32 ULID (48-bit ms time + 80-bit randomness)."""
    value = (int(time.time() * 1000) << 80) | int.from_bytes(os.urandom(10), "big")
    chars = []
    for _ in range(26):
        chars.append(_CROCKFORD[value & 0x1F])
        value >>= 5
    return "".join(reversed(chars))


def new_id(prefix: str) -> str:
    """New prefixed ID, e.g. ``hyp_01J...`` (prefix table in docs/12)."""
    return f"{prefix}_{_ulid()}"


def utcnow() -> datetime:
    return datetime.now(UTC)


class StrictModel(BaseModel):
    """All inbound and LLM-output models forbid unknown fields (docs/12)."""

    model_config = ConfigDict(extra="forbid", frozen=False, str_strip_whitespace=False)


ShortText = Annotated[str, StringConstraints(max_length=2000)]
LongText = Annotated[str, StringConstraints(max_length=8000)]
RelPath = Annotated[str, StringConstraints(min_length=1, max_length=400)]


class AgentName(StrEnum):
    SCOUT = "scout"
    PROBE = "probe"
    TRACE = "trace"
    DIAGNOSE = "diagnose"
    PATCH = "patch"
    FORTIFY = "fortify"
    VERIFY = "verify"


class Confidence(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


CONFIDENCE_WEIGHT: dict[Confidence, float] = {
    Confidence.LOW: 0.3,
    Confidence.MEDIUM: 0.6,
    Confidence.HIGH: 0.9,
}


class ErrorCode(StrEnum):
    SCOPE_DENIED = "SCOPE_DENIED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    SCHEMA_INVALID = "SCHEMA_INVALID"
    SANDBOX_START_FAILED = "SANDBOX_START_FAILED"
    SANDBOX_TIMEOUT = "SANDBOX_TIMEOUT"
    SANDBOX_POLICY_VIOLATION = "SANDBOX_POLICY_VIOLATION"
    TOOL_NOT_ALLOWED = "TOOL_NOT_ALLOWED"
    SNAPSHOT_NOT_READY = "SNAPSHOT_NOT_READY"
    LLM_UNAVAILABLE = "LLM_UNAVAILABLE"
    CONFLICT_STATE = "CONFLICT_STATE"
    CANCELLED = "CANCELLED"
    KILL_SWITCH = "KILL_SWITCH"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    INTERNAL = "INTERNAL"


class PlatformError(Exception):
    """An error carrying a catalog code. Raised by guards, tools and the runtime."""

    def __init__(self, code: ErrorCode, message: str) -> None:
        super().__init__(f"{code.value}: {message}")
        self.code = code
        self.message = message
