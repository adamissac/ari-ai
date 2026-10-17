from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from .catalog import load_json

PREFIX = "CVSS:3.1/"
BASE_ORDER = ("AV", "AC", "PR", "UI", "S", "C", "I", "A")
SCORE_KIND = "CVSS v3.1 base score only (severity, not risk)"

ALLOWED: dict[str, tuple[str, ...]] = {
    "AV": ("N", "A", "L", "P"),
    "AC": ("L", "H"),
    "PR": ("N", "L", "H"),
    "UI": ("N", "R"),
    "S": ("U", "C"),
    "C": ("H", "L", "N"),
    "I": ("H", "L", "N"),
    "A": ("H", "L", "N"),
}

LABELS: dict[str, dict[str, str]] = {
    "AV": {"N": "Network", "A": "Adjacent", "L": "Local", "P": "Physical"},
    "AC": {"L": "Low", "H": "High"},
    "PR": {"N": "None", "L": "Low", "H": "High"},
    "UI": {"N": "None", "R": "Required"},
    "S": {"U": "Unchanged", "C": "Changed"},
    "C": {"H": "High", "L": "Low", "N": "None"},
    "I": {"H": "High", "L": "Low", "N": "None"},
    "A": {"H": "High", "L": "Low", "N": "None"},
}

Rating = Literal["none", "low", "medium", "high", "critical"]


class CvssError(ValueError):
    pass


@dataclass(frozen=True)
class BaseMetrics:
    AV: str
    AC: str
    PR: str
    UI: str
    S: str
    C: str
    I: str  # noqa: E741 - CVSS specification metric identifier
    A: str

    def __post_init__(self) -> None:
        for key in BASE_ORDER:
            value = getattr(self, key)
            if value not in ALLOWED[key]:
                raise CvssError(f"{key}:{value} is not a CVSS v3.1 base metric value")

    def vector(self) -> str:
        return PREFIX + "/".join(f"{key}:{getattr(self, key)}" for key in BASE_ORDER)


@dataclass(frozen=True)
class BaseScore:
    vector: str
    score: float
    rating: Rating
    impact_subscore: float
    impact: float
    exploitability: float
    kind: str = SCORE_KIND


def parse_vector(vector: str) -> BaseMetrics:
    text = str(vector).strip()
    if not text.startswith(PREFIX):
        raise CvssError(f"vector must start with {PREFIX!r}")
    seen: dict[str, str] = {}
    for part in text[len(PREFIX) :].split("/"):
        if ":" not in part:
            raise CvssError(f"malformed metric {part!r}")
        key, value = part.split(":", 1)
        if key in seen:
            raise CvssError(f"metric {key} appears more than once")
        if key not in ALLOWED:
            raise CvssError(
                f"{key} is not a CVSS v3.1 base metric; this calculator is base score only"
            )
        seen[key] = value
    missing = [key for key in BASE_ORDER if key not in seen]
    if missing:
        raise CvssError(f"missing mandatory base metrics: {', '.join(missing)}")
    return BaseMetrics(**seen)


def roundup(value: float) -> float:
    int_input = math.floor(value * 100000 + 0.5)
    if int_input % 10000 == 0:
        return int_input / 100000.0
    return (math.floor(int_input / 10000) + 1) / 10.0


def _weights() -> dict[str, dict[str, float]]:
    return load_json("cvss-v3.1.json")["weights"]


def _constants() -> dict[str, float]:
    return load_json("cvss-v3.1.json")["constants"]


def rating_for(score: float) -> Rating:
    for band in load_json("cvss-v3.1.json")["rating_bands"]:
        if band["min"] <= score <= band["max"]:
            return band["rating"]
    raise CvssError(f"score {score} falls outside every CVSS v3.1 rating band")


def base_score(metrics: BaseMetrics) -> BaseScore:
    weights = _weights()
    constants = _constants()
    changed = metrics.S == "C"
    cia = weights["CIA"]
    confidentiality = cia[LABELS["C"][metrics.C]]
    integrity = cia[LABELS["I"][metrics.I]]
    availability = cia[LABELS["A"][metrics.A]]
    iss = 1 - ((1 - confidentiality) * (1 - integrity) * (1 - availability))
    if changed:
        impact = (
            constants["impact_changed_factor"] * (iss - constants["impact_changed_iss_offset"])
            - constants["impact_changed_subtrahend"]
            * (iss - constants["impact_changed_power_offset"]) ** constants["impact_changed_power"]
        )
    else:
        impact = constants["impact_unchanged_factor"] * iss
    privileges = weights["PR_scope_changed" if changed else "PR"][LABELS["PR"][metrics.PR]]
    exploitability = (
        constants["exploitability_factor"]
        * weights["AV"][LABELS["AV"][metrics.AV]]
        * weights["AC"][LABELS["AC"][metrics.AC]]
        * privileges
        * weights["UI"][LABELS["UI"][metrics.UI]]
    )
    if impact <= 0:
        score = 0.0
    elif changed:
        score = roundup(min(constants["scope_changed_multiplier"] * (impact + exploitability), 10))
    else:
        score = roundup(min(impact + exploitability, 10))
    return BaseScore(
        vector=metrics.vector(),
        score=score,
        rating=rating_for(score),
        impact_subscore=iss,
        impact=impact,
        exploitability=exploitability,
    )


def score_vector(vector: str) -> BaseScore:
    return base_score(parse_vector(vector))


SEVERITY_LEVEL_FROM_RATING: dict[str, str] = {
    "none": "info",
    "low": "low",
    "medium": "medium",
    "high": "high",
    "critical": "critical",
}


def severity_level(score: BaseScore) -> str:
    return SEVERITY_LEVEL_FROM_RATING[score.rating]
