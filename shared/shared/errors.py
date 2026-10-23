"""Error-code catalog (docs/12) and the API error envelope (docs/13)."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from shared.base import JsonObject, ShortText, StrictModel


class ErrorCode(StrEnum):
    # docs/12 catalog
    SCOPE_DENIED = "SCOPE_DENIED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    SCHEMA_INVALID = "SCHEMA_INVALID"
    SANDBOX_START_FAILED = "SANDBOX_START_FAILED"
    SANDBOX_TIMEOUT = "SANDBOX_TIMEOUT"
    SANDBOX_POLICY_VIOLATION = "SANDBOX_POLICY_VIOLATION"
    TOOL_NOT_ALLOWED = "TOOL_NOT_ALLOWED"
    SNAPSHOT_NOT_READY = "SNAPSHOT_NOT_READY"
    WEBHOOK_SIGNATURE_INVALID = "WEBHOOK_SIGNATURE_INVALID"
    LLM_UNAVAILABLE = "LLM_UNAVAILABLE"
    CONFLICT_STATE = "CONFLICT_STATE"
    # V0 additions (API and integration plumbing)
    LLM_REFUSAL = "LLM_REFUSAL"
    LLM_OUTPUT_TRUNCATED = "LLM_OUTPUT_TRUNCATED"
    UNAUTHENTICATED = "UNAUTHENTICATED"
    FORBIDDEN = "FORBIDDEN"
    CSRF_FAILED = "CSRF_FAILED"
    NOT_FOUND = "NOT_FOUND"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    RATE_LIMITED = "RATE_LIMITED"
    PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    SUBSYSTEM_UNAVAILABLE = "SUBSYSTEM_UNAVAILABLE"
    CANCELLED = "CANCELLED"
    JOB_LEASE_EXPIRED = "JOB_LEASE_EXPIRED"
    INTERNAL = "INTERNAL"
    # Agent-domain halt raised when the kill switch pauses assessments.
    KILL_SWITCH = "KILL_SWITCH"
    # Live Defense Phase 4: authorization gate denied a control (fail closed).
    LIVE_CONTROL_DENIED = "LIVE_CONTROL_DENIED"


class ErrorBody(StrictModel):
    code: ErrorCode
    message: ShortText
    details: JsonObject = Field(default_factory=dict)
    request_id: str | None = None


class ErrorResponse(StrictModel):
    error: ErrorBody
