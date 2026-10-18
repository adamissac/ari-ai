"""Canonical cross-subsystem contracts (single source of truth, ADR-0004).

Import models from their modules (``from shared.findings import Finding``) or from
``shared.registry`` for the full list. Owner: Srihith. Change procedure:
coordination/CONTRACTS.md.
"""

SCHEMA_VERSION = (
    "0.11.0"  # 0.2 RLExplanation; 0.3 runtime signals; 0.4 ids allow _-; 0.5 early REPORTING;
    # 0.6 intelligence memory (PR #39); 0.7 security standards + incidents (PR #49);
    # 0.8 FindingDetail / AssessmentReport response DTOs (additive);
    # 0.9 CheckCategory enum (Probe ids + V0 fixture aliases);
    # 0.10 SeverityAssessment.cvss_v31 (CVSS31Assessment, additive, ADR-0012);
    # 0.11 Assessment.repo_id (additive; findings link to the assessed repo)
)
