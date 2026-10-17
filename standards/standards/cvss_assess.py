"""Evidence -> CVSS v4.0 base metrics -> ``CVSSAssessment``.

The derivation is the reviewed table in ``data/rules/cvss_derivation.json``: each base
metric reads one recorded fact. If the fact is absent or has no case in the table, the
metric is *missing* and the assessment is returned incomplete, with no vector and no
score; nothing is guessed. Assumption-based values are listed on the assessment.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from shared.evidence import EvidenceRef
from shared.standards import CVSSAssessment, CVSSMetricBasis, CVSSMetricValue
from standards.catalog import load_json, manifest
from standards.cvss4 import BASE_METRICS, build_vector
from standards.cvss4 import score as cvss_score

ASSESSOR = "system:standards.cvss_assess@1"


@dataclass(frozen=True)
class Fact:
    value: str
    evidence: list[EvidenceRef] = field(default_factory=list)


def scoring_engine() -> str:
    upstream = manifest()["files"]["cvss-v4.0.json"]["upstream"][0]["url"]
    commit = upstream.split("/")[-2]
    return f"standards.cvss4 (port of FIRST cvss-v4-calculator@{commit[:12]})"


def _fact_for(key: str, facts: dict[str, Fact]) -> Fact | None:
    if "|" not in key:
        return facts.get(key)
    parts = [facts.get(k) for k in key.split("|")]
    if any(p is None for p in parts):
        return None
    evidence: list[EvidenceRef] = []
    for p in parts:
        evidence.extend(p.evidence)  # type: ignore[union-attr]
    return Fact("|".join(p.value for p in parts), evidence)  # type: ignore[union-attr]


def assess(
    facts: dict[str, Fact],
    *,
    now: datetime,
    overrides: dict[str, CVSSMetricValue] | None = None,
    assessor: str = ASSESSOR,
) -> CVSSAssessment:
    """Derive base metrics from facts (human ``overrides`` win) and score if complete."""
    table = load_json("rules/cvss_derivation.json")["metrics"]
    overrides = overrides or {}
    values: list[CVSSMetricValue] = []
    missing: list[str] = []
    for metric in BASE_METRICS:
        if metric in overrides:
            values.append(overrides[metric])
            continue
        rule = table[metric]
        fact = _fact_for(rule["fact"], facts)
        case = rule["cases"].get(fact.value) if fact else None
        if case is None:
            missing.append(metric)
            continue
        basis = CVSSMetricBasis(case["basis"])
        values.append(
            CVSSMetricValue(
                metric=metric,  # type: ignore[arg-type]
                value=case["value"],
                basis=basis,
                rationale=case["rationale"],
                evidence=list(fact.evidence) if fact else [],
            )
        )
    assumptions = [
        f"{v.metric}:{v.value} - {v.rationale}"
        for v in values
        if v.basis is CVSSMetricBasis.assumption
    ]
    common = dict(
        metrics=values,
        assumptions=assumptions,
        assessor=assessor,
        scoring_engine=scoring_engine(),
        assessed_at=now,
    )
    if missing:
        return CVSSAssessment(
            complete=False,
            missing_metrics=missing,
            rationale=(
                "Incomplete: the recorded evidence does not determine "
                + ", ".join(missing)
                + ". No score is computed until a human supplies these metrics."
            ),
            **common,  # type: ignore[arg-type]
        )
    vector = build_vector({v.metric: v.value for v in values})
    result = cvss_score(vector)
    return CVSSAssessment(
        complete=True,
        vector=vector,
        score=result.score,
        severity=result.severity,  # type: ignore[arg-type]
        nomenclature=result.nomenclature,  # type: ignore[arg-type]
        rationale=(
            f"Base score computed from {len(values)} metrics"
            + (f" ({len(assumptions)} by documented assumption)" if assumptions else "")
            + "; threat and environmental metrics not assessed."
        ),
        **common,  # type: ignore[arg-type]
    )
