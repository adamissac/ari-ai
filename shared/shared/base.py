"""Base model, primitive types and validators used by every contract."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Annotated, Any

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints


class StrictModel(BaseModel):
    """Base for every contract model.

    * Unknown fields are rejected (``extra="forbid"``) so producers cannot silently
      drift from the schema and LLM output with invented fields fails validation.
    * Enum/Literal fields only accept declared values.
    * Datetimes must be timezone-aware UTC (see ``UtcDatetime``).
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        populate_by_name=False,
        use_enum_values=False,
        ser_json_timedelta="float",
        # Fields with defaults are always present in serialized output, so the
        # generated TypeScript marks them required for consumers.
        json_schema_serialization_defaults_required=True,
    )


def _require_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware UTC")
    if value.utcoffset().total_seconds() != 0:  # type: ignore[union-attr]
        raise ValueError("timestamp must be in UTC (offset +00:00)")
    return value.astimezone(UTC)


UtcDatetime = Annotated[datetime, AfterValidator(_require_utc)]
"""ISO-8601 timestamp with explicit UTC offset; naive datetimes are rejected."""

CommitSha = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{40}$")]
"""Full 40-hex lowercase Git commit SHA. Abbreviated SHAs are not accepted."""

Sha256Hex = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


def _repo_rel_path(value: str) -> str:
    if value.startswith("/") or "\\" in value or "\x00" in value:
        raise ValueError("path must be repository-relative POSIX")
    if any(part == ".." for part in value.split("/")):
        raise ValueError("path must not contain '..' segments")
    return value


RepoRelPath = Annotated[
    str, StringConstraints(min_length=1, max_length=1024), AfterValidator(_repo_rel_path)
]
"""Repository-relative POSIX path; absolute paths and ``..`` segments are rejected."""

ShortText = Annotated[str, StringConstraints(max_length=500)]
LongText = Annotated[str, StringConstraints(max_length=20_000)]

Confidence = Annotated[float, Field(ge=0.0, le=1.0)]

JsonObject = dict[str, Any]


def utcnow() -> datetime:
    return datetime.now(UTC)


_SECRETISH = re.compile(
    r"(sk-ant-[A-Za-z0-9_\-]{8,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}"
    r"|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----)"
)


def looks_like_secret(text: str) -> bool:
    """Cheap tripwire for credential-shaped strings in persisted payloads."""
    return bool(_SECRETISH.search(text))
