"""CVSS v4.0 base vectors using Red Hat's pinned reference implementation.

Legacy SeverityFactors free text does not determine the eleven base metrics.
Callers must supply explicit, evidence-backed metrics; missing evidence stays
unscored, rather than silently becoming a numeric severity claim.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from standards import cvss4

BASE_METRICS = ("AV", "AC", "AT", "PR", "UI", "VC", "VI", "VA", "SC", "SI", "SA")


def vector(metrics: Mapping[str, str] | Any) -> str:
    if hasattr(metrics, "model_dump"):
        metrics = metrics.model_dump()
    if not isinstance(metrics, Mapping):
        raise ValueError("Explicit CVSS v4.0 metrics are required")
    missing = set(BASE_METRICS) - metrics.keys()
    if missing:
        raise ValueError(f"Missing CVSS base metrics: {sorted(missing)}")
    if set(metrics) - set(BASE_METRICS):
        raise ValueError("Only CVSS v4.0 base metrics are accepted")
    result = "CVSS:4.0/" + "/".join(f"{key}:{metrics[key]}" for key in BASE_METRICS)
    _parse(result)
    return result


def score(value: str) -> tuple[float, str]:
    parsed = _parse(value)
    parts = value.split("/")[1:]
    keys = [part.split(":", 1)[0] for part in parts]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate CVSS metrics are prohibited")
    # Deliberately reject optional Threat/Environmental/Supplemental metrics:
    # this API promises a base score, not a context-dependent combined score.
    fields = dict(item.split(":", 1) for item in value.split("/")[1:])
    if set(fields) != set(BASE_METRICS):
        raise ValueError("Only complete CVSS v4.0 base vectors are accepted")
    return parsed.score, parsed.severity


def from_factors(factors: Any, *, metrics: Mapping[str, str] | None = None) -> dict[str, str]:
    """Validate explicit metrics; legacy reachability prose cannot imply impacts.

    No metric is inferred from SeverityFactors. For every metric (AV, AC, AT,
    PR, UI, VC, VI, VA, SC, SI, SA), explicit assessment evidence is required.
    Incomplete callers receive ValueError and should retain cvss=None.
    """
    if metrics is None:
        raise ValueError(
            "SeverityFactors are insufficient; explicit evidence-backed metrics required"
        )
    vector(metrics)
    return dict(metrics)


def _parse(value: str) -> cvss4.CVSSResult:
    return cvss4.score(value)
