"""Validation and derivation of framework mappings.

Rules enforced here (each has a test):

* an identifier must exist in the pinned catalog release, else ``MappingRejected``;
* deprecated or revoked identifiers are refused for new mappings (the replacement, when
  the catalog names one, is reported) and only accepted as flagged legacy imports;
* CWE classifications must target entries whose own mapping guidance allows it: CWE
  categories/views and entries marked ``Prohibited`` are refused; ``Discouraged`` is
  refused unless a human makes the mapping;
* every mapping cites at least one piece of evidence;
* ATT&CK and D3FEND mappings come only from reviewed rule tables or a human. The
  CWE -> CAPEC -> ATT&CK catalog chain is exposed as *candidates for review* and never
  attached automatically, because the catalogs' links are too coarse to justify a mapping
  (see ``attack_candidates_via_capec``).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from typing import Any

from shared.evidence import EvidenceRef
from shared.standards import (
    CatalogStatus,
    ControlStatus,
    CWEClassification,
    DefensiveMapping,
    MappedVia,
    Observation,
    ReviewStatus,
    StandardFramework,
    StandardMapping,
)
from standards import catalog
from standards.catalog import CatalogEntry, UnknownIdentifier, load_json


class MappingRejected(ValueError):
    """A proposed mapping is not supported by the catalog or the evidence."""

    def __init__(self, code: str, message: str, *, replaced_by: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.replaced_by = replaced_by


@dataclass(frozen=True)
class Unmapped:
    framework: str
    reason: str

    def text(self) -> str:
        return f"{self.framework}: {self.reason}"


_FRAMEWORK_TO_CATALOG: dict[StandardFramework, catalog.Framework] = {
    StandardFramework.attack: "attack",
    StandardFramework.d3fend: "d3fend",
    StandardFramework.cwe: "cwe",
    StandardFramework.owasp_llm: "owasp_llm",
    StandardFramework.nist_csf: "nist_csf",
}


def resolve(
    framework: StandardFramework, identifier: str, *, allow_inactive: bool = False
) -> CatalogEntry:
    """Catalog entry for ``identifier`` or ``MappingRejected`` (unknown / inactive)."""
    try:
        entry = catalog.lookup(_FRAMEWORK_TO_CATALOG[framework], identifier)
    except UnknownIdentifier as exc:
        raise MappingRejected("unknown_identifier", str(exc).strip("'\"")) from exc
    if entry.status != "active" and not allow_inactive:
        hint = f"; replaced by {entry.replaced_by}" if entry.replaced_by else ""
        raise MappingRejected(
            f"{entry.status}_identifier",
            f"{identifier} is {entry.status} in {framework.value} {entry.catalog_version}{hint}",
            replaced_by=entry.replaced_by,
        )
    return entry


def build_mapping(
    framework: StandardFramework,
    identifier: str,
    *,
    mapped_via: MappedVia,
    observation: Observation,
    rationale: str,
    confidence: float,
    evidence: list[EvidenceRef],
    rule_id: str | None = None,
) -> StandardMapping:
    if not evidence:
        raise MappingRejected(
            "insufficient_evidence", f"{identifier}: a mapping must cite evidence"
        )
    entry = resolve(framework, identifier)
    return StandardMapping(
        framework=framework,
        id=entry.id,
        name=entry.name,
        catalog_version=entry.catalog_version,
        url=entry.url,
        mapped_via=mapped_via,
        rule_id=rule_id,
        observation=observation,
        rationale=rationale[:500],
        confidence=confidence,
        evidence=evidence,
    )


def import_legacy(
    framework: StandardFramework,
    identifier: str,
    *,
    source_version: str,
    rationale: str,
    evidence: list[EvidenceRef],
) -> StandardMapping:
    """Keep a mapping made under an older release, flagged, with its current catalog status."""
    entry = resolve(framework, identifier, allow_inactive=True)
    note = f"imported from {framework.value} {source_version}; current status {entry.status}"
    if entry.replaced_by:
        note += f", replaced by {entry.replaced_by}"
    return StandardMapping(
        framework=framework,
        id=entry.id,
        name=entry.name,
        catalog_version=entry.catalog_version,
        url=entry.url,
        catalog_status=CatalogStatus(entry.status),
        mapped_via=MappedVia.human,
        observation=Observation.hypothesis,
        rationale=f"{rationale} ({note})"[:500],
        confidence=0.0 if entry.status != "active" else 0.5,
        evidence=evidence,
        legacy=True,
    )


# ------------------------------------------------------------------ CWE


def check_cwe(identifier: str, *, by_human: bool = False) -> CatalogEntry:
    """Validate a CWE id for root-cause classification under CWE's own mapping guidance."""
    entry = resolve(StandardFramework.cwe, identifier)
    usage = entry.detail.get("mapping_usage")
    if entry.detail.get("kind") != "weakness":
        raise MappingRejected(
            "not_a_weakness",
            f"{identifier} is a CWE {entry.detail.get('kind')} ({usage}); map root causes to weaknesses",
        )
    if usage == "Prohibited":
        raise MappingRejected(
            "mapping_prohibited", f"CWE marks {identifier} as Prohibited for mapping"
        )
    if usage == "Discouraged" and not by_human:
        raise MappingRejected(
            "mapping_discouraged",
            f"CWE marks {identifier} ({entry.name}) as Discouraged for mapping; choose a more specific weakness",
        )
    return entry


def classify_cwe(
    identifier: str,
    *,
    observation: Observation,
    mapped_via: MappedVia,
    rationale: str,
    confidence: float,
    evidence: list[EvidenceRef],
    by_human: bool = False,
) -> CWEClassification:
    if not evidence:
        raise MappingRejected(
            "insufficient_evidence", f"{identifier}: a classification must cite evidence"
        )
    entry = check_cwe(identifier, by_human=by_human)
    return CWEClassification(
        framework=StandardFramework.cwe,
        id=entry.id,
        name=entry.name,
        catalog_version=entry.catalog_version,
        url=entry.url,
        mapped_via=mapped_via,
        observation=observation,
        rationale=rationale[:500],
        confidence=confidence,
        evidence=evidence,
        mapping_usage=entry.detail.get("mapping_usage"),
    )


# ------------------------------------------------------------------ rule tables


@cache
def _rules(name: str) -> dict[str, Any]:
    return dict(load_json(f"rules/{name}.json"))


def _unmapped_reason(table: dict[str, Any], key: str) -> str:
    reasons = table.get("unmapped", {})
    return str(reasons.get(key) or reasons.get("*") or "no reviewed rule")


def attack_for_check(
    check_category: str,
    facts: dict[str, str],
    *,
    observation: Observation,
    evidence: list[EvidenceRef],
) -> tuple[list[StandardMapping], list[Unmapped]]:
    table = _rules("check_attack")
    out: list[StandardMapping] = []
    for rule in table["rules"]:
        if rule["check_category"] != check_category:
            continue
        if any(facts.get(k) not in allowed for k, allowed in rule.get("conditions", {}).items()):
            continue
        out.append(
            build_mapping(
                StandardFramework.attack,
                rule["technique"],
                mapped_via=MappedVia.check_template_rule,
                observation=observation,
                rationale=rule["rationale"],
                confidence=float(rule["confidence"]),
                evidence=evidence,
                rule_id=rule["rule_id"],
            )
        )
    if out:
        return out, []
    return [], [Unmapped("attack", _unmapped_reason(table, check_category))]


def _defensive(
    rule: dict[str, Any],
    *,
    evidence: list[EvidenceRef],
    control_status: ControlStatus,
    hardening_id: str | None,
    simulation_derived: bool,
    observation: Observation,
) -> DefensiveMapping:
    base = build_mapping(
        StandardFramework.d3fend,
        rule["technique"],
        mapped_via=MappedVia.reviewed_rule_table,
        observation=observation,
        rationale=rule["rationale"],
        confidence=float(rule["confidence"]),
        evidence=evidence,
        rule_id=rule["rule_id"],
    )
    return DefensiveMapping(
        **base.model_dump(),
        control_status=control_status,
        hardening_id=hardening_id,
        simulation_derived=simulation_derived,
    )


def d3fend_for_hardening(
    fortify_category: str,
    check_category: str,
    *,
    evidence: list[EvidenceRef],
    hardening_id: str | None = None,
    control_status: ControlStatus = ControlStatus.proposed,
) -> tuple[list[DefensiveMapping], list[Unmapped]]:
    table = _rules("fortify_d3fend")
    out = [
        _defensive(
            rule,
            evidence=evidence,
            control_status=control_status,
            hardening_id=hardening_id,
            simulation_derived=False,
            observation=Observation.hypothesis,
        )
        for rule in table["rules"]
        if rule["fortify_category"] == fortify_category
        and rule["check_category"] in (check_category, "*")
    ]
    if out:
        return out, []
    return [], [
        Unmapped("d3fend", f"{fortify_category}: {_unmapped_reason(table, fortify_category)}")
    ]


def d3fend_for_rl_action(
    action: str, *, evidence: list[EvidenceRef]
) -> tuple[list[DefensiveMapping], list[Unmapped]]:
    table = _rules("rl_d3fend")
    out = [
        _defensive(
            rule,
            evidence=evidence,
            control_status=ControlStatus.proposed,
            hardening_id=None,
            simulation_derived=True,
            observation=Observation.simulated,
        )
        for rule in table["rules"]
        if rule["action"] == action
    ]
    if out:
        return out, []
    return [], [Unmapped("d3fend", f"{action}: {_unmapped_reason(table, action)}")]


# ------------------------------------------------------------------ catalog chain (review only)


@dataclass(frozen=True)
class ChainCandidate:
    technique: str
    via_capec: str
    status: str
    name: str | None
    note: str


def attack_candidates_via_capec(cwe_id: str) -> list[ChainCandidate]:
    """CWE -> CAPEC -> ATT&CK links straight from the catalogs, each checked against ATT&CK.

    These are leads for a human reviewer, not mappings: CAPEC's ATT&CK links describe the
    attack pattern in general (often host-level techniques) and CAPEC 3.9 predates ATT&CK
    20.0, so links may point at revoked or deprecated techniques.
    """
    out: list[ChainCandidate] = []
    for capec_id in catalog.capec_for_cwe(cwe_id):
        for technique in catalog.attack_for_capec(capec_id):
            try:
                entry = catalog.attack_technique(technique)
                note = (
                    f"{entry.status}; replaced by {entry.replaced_by}"
                    if entry.replaced_by
                    else entry.status
                )
                out.append(ChainCandidate(technique, capec_id, entry.status, entry.name, note))
            except UnknownIdentifier:
                out.append(
                    ChainCandidate(
                        technique, capec_id, "unknown", None, "not in the pinned ATT&CK release"
                    )
                )
    return out


def review(mapping: StandardMapping, *, reviewer: str, accept: bool) -> StandardMapping:
    """Record a human review decision on a mapping (the only way out of ``proposed``)."""
    if not reviewer.startswith("user:"):
        raise MappingRejected("reviewer_not_human", "only a human user can review a mapping")
    return type(mapping).model_validate(
        {
            **mapping.model_dump(),
            "review_status": ReviewStatus.accepted if accept else ReviewStatus.rejected,
            "reviewed_by": reviewer,
        }
    )
