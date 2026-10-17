"""Security standards classifications attached to findings (contract 0.7.0, additive).

These are *shapes only*. Identifiers are validated against pinned catalogs and CVSS
scores are computed by deterministic code in the ``standards`` package; a model may
propose a mapping, but nothing here is accepted on a model's say-so:

* every mapping names the catalog release it was validated against;
* every mapping cites evidence and records how it was derived (``mapped_via``);
* ``observation`` keeps executed sandbox reproduction, runtime signals, simulation and
  static hypotheses apart, so a classification is never presented as observed adversary
  behaviour it is not;
* defensive mappings separate *proposed* from *implemented* from *tested* controls.

Technical severity (CVSS), business priority, exploit confirmation and confidence are
separate fields on purpose (docs/decisions/ADR-0010).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from shared.base import Confidence, ShortText, StrictModel, UtcDatetime
from shared.evidence import EvidenceKind, EvidenceRef
from shared.ids import HardeningId


class StandardFramework(StrEnum):
    attack = "attack"
    d3fend = "d3fend"
    cwe = "cwe"
    owasp_llm = "owasp_llm"
    nist_csf = "nist_csf"


class MappedVia(StrEnum):
    """How a mapping was derived. Never ``model``: model proposals go through ``rule``/``human``."""

    check_template_rule = "check_template_rule"  # reviewed rule table keyed by an executed check
    catalog_relation = (
        "catalog_relation"  # e.g. CWE -> CAPEC -> ATT&CK from the catalogs' own links
    )
    reviewed_rule_table = "reviewed_rule_table"  # e.g. Fortify category -> D3FEND
    validated_proposal = "validated_proposal"  # agent-proposed id, validated against the catalog
    human = "human"


class Observation(StrEnum):
    """What kind of evidence the mapping rests on."""

    observed_in_sandbox = (
        "observed_in_sandbox"  # an executed check reproduced it in an authorized sandbox
    )
    observed_runtime = "observed_runtime"  # a runtime monitoring signal; not a confirmed incident
    simulated = "simulated"  # RL environment, replay or scripted fixture
    hypothesis = "hypothesis"  # static reasoning only; nothing executed


class ReviewStatus(StrEnum):
    proposed = "proposed"
    accepted = "accepted"
    rejected = "rejected"


class CatalogStatus(StrEnum):
    active = "active"
    deprecated = "deprecated"
    revoked = "revoked"


class StandardMapping(StrictModel):
    framework: StandardFramework
    id: ShortText = Field(
        description="Catalog identifier, e.g. T1190, D3-AMED, CWE-639, LLM01:2025"
    )
    name: ShortText = Field(description="Name from the catalog, never model text")
    catalog_version: ShortText
    url: ShortText | None = None
    catalog_status: CatalogStatus = CatalogStatus.active
    mapped_via: MappedVia
    rule_id: ShortText | None = Field(default=None, description="Rule-table row that produced it")
    observation: Observation
    rationale: ShortText
    confidence: Confidence
    evidence: list[EvidenceRef] = Field(min_length=1)
    review_status: ReviewStatus = ReviewStatus.proposed
    reviewed_by: ShortText | None = None
    legacy: bool = Field(default=False, description="Imported under an older catalog release")

    @model_validator(mode="after")
    def _consistent(self) -> StandardMapping:
        from standards.catalog import lookup

        try:
            entry = lookup(self.framework.value, self.id)
        except KeyError as exc:
            raise ValueError(f"unknown {self.framework.value} identifier: {self.id}") from exc
        if (
            self.name != entry.name
            or self.catalog_version != entry.catalog_version
            or self.catalog_status.value != entry.status
        ):
            raise ValueError("standard name, version and status must match the pinned catalog")
        if self.catalog_status is not CatalogStatus.active and not self.legacy:
            raise ValueError("deprecated or revoked identifiers are only allowed on legacy imports")
        if self.review_status is not ReviewStatus.proposed and not self.reviewed_by:
            raise ValueError("accepted/rejected mappings must name the human reviewer")
        if self.observation is Observation.observed_in_sandbox and not any(
            e.kind in (EvidenceKind.sandbox_run, EvidenceKind.test_run) for e in self.evidence
        ):
            raise ValueError("observed_in_sandbox requires sandbox_run or test_run evidence")
        return self


class ControlStatus(StrEnum):
    proposed = "proposed"  # recommended, nothing changed
    implemented = "implemented"  # a change exists (patch/config) but no executed test proves it
    tested = "tested"  # an executed test exercised the control and passed


class DefensiveMapping(StandardMapping):
    control_status: ControlStatus = ControlStatus.proposed
    hardening_id: HardeningId | None = None
    simulation_derived: bool = False

    @model_validator(mode="after")
    def _tested_needs_tests(self) -> DefensiveMapping:
        if self.framework is not StandardFramework.d3fend:
            raise ValueError("defensive mappings must be D3FEND techniques")
        if self.control_status is ControlStatus.tested and not any(
            e.kind in (EvidenceKind.test_run, EvidenceKind.sandbox_run) for e in self.evidence
        ):
            raise ValueError("a 'tested' control requires executed test evidence")
        if self.simulation_derived and self.control_status is not ControlStatus.proposed:
            raise ValueError("simulation-derived countermeasures can only be proposals")
        return self


class CWEClassification(StandardMapping):
    mapping_usage: ShortText | None = Field(
        default=None, description="CWE's own Mapping_Notes/Usage for this entry (e.g. Allowed)"
    )

    @model_validator(mode="after")
    def _is_cwe(self) -> CWEClassification:
        if self.framework is not StandardFramework.cwe:
            raise ValueError("CWE classification must use the cwe framework")
        return self


class CVSSMetricBasis(StrEnum):
    evidence = "evidence"  # determined by cited evidence
    rule = "rule"  # determined by a reviewed derivation rule over cited evidence
    assumption = "assumption"  # not determined by evidence; documented assumption
    human = "human"


class CVSSMetricValue(StrictModel):
    metric: Literal["AV", "AC", "AT", "PR", "UI", "VC", "VI", "VA", "SC", "SI", "SA"]
    value: ShortText
    basis: CVSSMetricBasis
    rationale: ShortText
    evidence: list[EvidenceRef] = Field(default_factory=list)

    @model_validator(mode="after")
    def _evidence_backed(self) -> CVSSMetricValue:
        if self.basis in (CVSSMetricBasis.evidence, CVSSMetricBasis.rule) and not self.evidence:
            raise ValueError("evidence/rule-based metric values must cite evidence")
        return self


class CVSSAssessment(StrictModel):
    """A CVSS v4.0 base assessment. ``score`` is computed, never supplied by a model."""

    version: Literal["4.0"] = "4.0"
    vector: ShortText | None = Field(default=None, description="Present only when complete")
    score: float | None = Field(default=None, ge=0, le=10)
    severity: Literal["none", "low", "medium", "high", "critical"] | None = None
    nomenclature: Literal["CVSS-B", "CVSS-BT", "CVSS-BE", "CVSS-BTE"] | None = None
    metrics: list[CVSSMetricValue] = Field(default_factory=list)
    complete: bool
    missing_metrics: list[ShortText] = Field(default_factory=list)
    assumptions: list[ShortText] = Field(default_factory=list)
    rationale: ShortText
    assessor: ShortText = Field(
        description="'system:standards.cvss_assess@<ver>' or 'user:<usr_id>'"
    )
    scoring_engine: ShortText = Field(description="Implementation and pinned reference version")
    assessed_at: UtcDatetime

    @model_validator(mode="after")
    def _complete_iff_scored(self) -> CVSSAssessment:
        scored = self.score is not None and self.vector is not None and self.severity is not None
        if self.complete and (not scored or self.missing_metrics):
            raise ValueError(
                "a complete assessment needs vector, score, severity and no missing metrics"
            )
        if not self.complete and (self.score is not None or not self.missing_metrics):
            raise ValueError("an incomplete assessment lists missing metrics and has no score")
        if self.complete:
            from standards.cvss4 import BASE_METRICS, build_vector, score

            result = score(self.vector or "")
            if self.score != result.score or self.severity != result.severity:
                raise ValueError("CVSS score and severity must match deterministic scoring")
            if self.nomenclature != result.nomenclature:
                raise ValueError("CVSS nomenclature must match the scored vector")
            values = {m.metric: m.value for m in self.metrics}
            if len(values) != len(self.metrics) or set(values) != set(BASE_METRICS):
                raise ValueError("complete CVSS requires each base metric exactly once")
            if build_vector(values) != self.vector:
                raise ValueError("CVSS metric values must match the vector")
        return self


class LegacyScore(StrictModel):
    """A score imported from elsewhere, kept verbatim with its scoring system and version."""

    system: Literal["cvss"] = "cvss"
    version: Literal["2.0", "3.0", "3.1", "4.0"]
    vector: ShortText
    score: float = Field(ge=0, le=10)
    source: ShortText
    imported_at: UtcDatetime


class ExploitStatus(StrEnum):
    not_tested = "not_tested"
    reproduced_in_sandbox = "reproduced_in_sandbox"
    not_reproduced = "not_reproduced"


class BusinessPriority(StrEnum):
    unset = "unset"
    p1 = "p1"
    p2 = "p2"
    p3 = "p3"
    p4 = "p4"


class FindingStandards(StrictModel):
    """Standards view of one finding. Every entry carries its own catalog version and evidence."""

    cwe: CWEClassification | None = None
    attack: list[StandardMapping] = Field(default_factory=list)
    d3fend: list[DefensiveMapping] = Field(default_factory=list)
    cvss: CVSSAssessment | None = None
    legacy_scores: list[LegacyScore] = Field(default_factory=list)
    exploit_status: ExploitStatus = ExploitStatus.not_tested
    business_priority: BusinessPriority = Field(
        default=BusinessPriority.unset, description="Set by a human; independent of CVSS"
    )
    unmapped: list[ShortText] = Field(
        default_factory=list,
        description="Why a framework was left unmapped (insufficient evidence, no catalog relation)",
    )
    catalog_versions: dict[str, str] = Field(default_factory=dict)
    classified_by: ShortText
    classified_at: UtcDatetime

    @model_validator(mode="after")
    def _frameworks_match(self) -> FindingStandards:
        if any(m.framework is not StandardFramework.attack for m in self.attack):
            raise ValueError("attack list may only hold ATT&CK mappings")
        return self
