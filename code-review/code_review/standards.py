"""Optional evidence-backed CWE classification for reviewer proposals."""

from datetime import UTC, datetime

from shared.evidence import EvidenceRef
from shared.standards import FindingStandards, MappedVia, Observation
from standards.catalog import catalog_versions
from standards.mapping import classify_cwe


def classify_weakness(
    identifier: str | None, evidence: list[EvidenceRef], confidence: float
) -> FindingStandards | None:
    if not identifier:
        return None
    return FindingStandards(
        cwe=classify_cwe(
            identifier,
            observation=Observation.hypothesis,
            mapped_via=MappedVia.validated_proposal,
            rationale="Reviewer-proposed weakness classification",
            confidence=confidence,
            evidence=evidence,
        ),
        classified_by="agent:reviewer",
        classified_at=datetime.now(UTC),
        catalog_versions=catalog_versions(),
    )
