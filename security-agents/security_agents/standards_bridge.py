"""Standards view of a security finding: CWE, ATT&CK, D3FEND and a CVSS v4.0 assessment.

Everything here is deterministic. Identifiers come from the pinned catalogs; ATT&CK and
D3FEND come from reviewed rule tables; CVSS metrics are derived from facts the pipeline
already recorded (Probe's executed check, Trace's severity factors) and scored by the
port of FIRST's calculator. The only model-originated identifier is Scout's CWE, and
that is catalog-validated before it can become a record.

A fact the pipeline did not establish is left out, so the CVSS assessment stays
incomplete with no score rather than guessing. Fortify mappings stay *proposed*.
Trace's optional eleven-metric dict is *not* used here; it may still appear on
``SeverityAssessment.cvss`` as a provisional annotation.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from shared.standards import ExploitStatus, FindingStandards, MappedVia, Observation
from standards import catalog
from standards.cvss_assess import Fact, assess
from standards.mapping import MappingRejected, attack_for_check, classify_cwe

from .contracts import ValidationOutcome
from .contracts import export as contract_export

if TYPE_CHECKING:
    from .workflow.orchestrator import FindingRecord

CLASSIFIER = "system:security_agents.standards_bridge@1"


def _evidence(refs: list[Any], producer: str) -> list[Any]:
    return [contract_export.evidence_ref(r, producer=producer) for r in refs]


def _facts(finding: FindingRecord) -> dict[str, Fact]:
    facts: dict[str, Fact] = {}
    validation = finding.validation
    confirmed = validation is not None and validation.outcome is ValidationOutcome.CONFIRMED
    if confirmed and validation is not None and validation.check_template_id:
        run = _evidence(validation.evidence, "agent:probe")
        facts["check_outcome"] = Fact("confirmed", run)
        facts["check_interaction"] = Fact("direct_request", run)
        facts["check_category"] = Fact(validation.check_template_id, run)
        facts["subsequent_impact"] = Fact("not_exercised", run)
    if finding.severity is not None:
        factors = finding.severity.factors
        path_ev = (
            _evidence([e for s in finding.attack_path.steps for e in s.evidence], "agent:trace")
            if finding.attack_path
            else []
        ) or _evidence(finding.hypothesis.cited_spans, "agent:trace")
        facts["reachability"] = Fact(factors.reachability, path_ev)
        facts["privileges_required"] = Fact(factors.privileges_required, path_ev)
        facts["data_sensitivity"] = Fact(factors.data_sensitivity, path_ev)
    if finding.attack_path is not None:
        facts["attack_preconditions"] = Fact(
            "recorded" if finding.attack_path.preconditions else "none_recorded",
            _evidence(finding.hypothesis.cited_spans, "agent:trace"),
        )
    return facts


def finding_standards(finding: FindingRecord, *, now: datetime) -> FindingStandards:
    """Classify one finding from what the pipeline has recorded so far."""
    unmapped: list[str] = []
    validation = finding.validation
    confirmed = validation is not None and validation.outcome is ValidationOutcome.CONFIRMED
    cited = _evidence(finding.hypothesis.cited_spans, "agent:scout")
    run = _evidence(validation.evidence, "agent:probe") if validation else []
    observation = Observation.observed_in_sandbox if confirmed and run else Observation.hypothesis

    cwe = None
    try:
        cwe = classify_cwe(
            finding.hypothesis.weakness_class,
            observation=observation,
            mapped_via=MappedVia.validated_proposal,
            rationale=f"Scout proposed {finding.hypothesis.weakness_class}; "
            + ("Probe's executed check confirmed it." if confirmed else "not yet confirmed."),
            confidence=contract_export.CONFIDENCE_SCORE[finding.hypothesis.confidence],
            evidence=cited + run,
        )
    except MappingRejected as exc:
        unmapped.append(f"cwe: {exc}")

    attack: list[Any] = []
    if confirmed and validation is not None and validation.check_template_id:
        facts = {}
        if finding.severity is not None:
            facts["reachability"] = finding.severity.factors.reachability
        attack, none = attack_for_check(
            validation.check_template_id,
            facts,
            observation=observation,
            evidence=cited + run,
        )
        unmapped += [u.text() for u in none]
    else:
        unmapped.append("attack: no executed check confirmed the hypothesis")

    d3fend = [ref for rec in finding.recommendations for ref in rec.d3fend]

    if validation is None:
        exploit = ExploitStatus.not_tested
    elif confirmed:
        exploit = ExploitStatus.reproduced_in_sandbox
    else:
        exploit = ExploitStatus.not_reproduced

    return FindingStandards(
        cwe=cwe,
        attack=attack,
        d3fend=d3fend,
        cvss=assess(_facts(finding), now=now),
        exploit_status=exploit,
        unmapped=[u[:500] for u in unmapped],
        catalog_versions=catalog.catalog_versions(),
        classified_by=CLASSIFIER,
        classified_at=now,
    )


def summary(standards: FindingStandards | None) -> dict[str, Any] | None:
    if standards is None:
        return None
    cvss = standards.cvss
    return {
        "cwe": standards.cwe.id if standards.cwe else None,
        "attack": [m.id for m in standards.attack],
        "d3fend": [m.id for m in standards.d3fend],
        "cvss_vector": cvss.vector if cvss else None,
        "cvss_score": cvss.score if cvss else None,
        "cvss_complete": bool(cvss and cvss.complete),
        "cvss_missing": list(cvss.missing_metrics) if cvss else [],
        "exploit_status": standards.exploit_status.value,
        "unmapped": list(standards.unmapped),
        "catalog_versions": dict(standards.catalog_versions),
    }
