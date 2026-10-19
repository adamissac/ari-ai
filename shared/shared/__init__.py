"""Canonical cross-subsystem contracts (single source of truth, ADR-0004).

Import models from their modules (``from shared.findings import Finding``) or from
``shared.registry`` for the full list. Owner: Srihith. Change procedure:
coordination/CONTRACTS.md.
"""

SCHEMA_VERSION = (
    "0.13.0"  # 0.2 RLExplanation; 0.3 runtime signals; 0.4 ids allow _-; 0.5 early REPORTING;
    # 0.6 intelligence memory (PR #39); 0.7 security standards + incidents (PR #49);
    # 0.8 FindingDetail / AssessmentReport response DTOs (additive);
    # 0.9 CheckCategory enum (Probe ids + V0 fixture aliases);
    # 0.10 SeverityAssessment.cvss_v31 (CVSS31Assessment, additive, ADR-0012);
    # 0.11 Assessment.repo_id (additive; findings link to the assessed repo);
    # 0.12 RuntimeSource "drill" (additive; attack drills get their own scoring history);
    # 0.13 live RL lab (additive): DefenseActionName "block_principal" (#324),
    #      "block_principal_long", "block_top_principal_long"; PlatformFacts principal-block
    #      and v3 detector fields with defaults (#334, #335; old payloads validate unchanged)
)
