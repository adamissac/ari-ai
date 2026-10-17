"""Canonical cross-subsystem contracts (single source of truth, ADR-0004).

Import models from their modules (``from shared.findings import Finding``) or from
``shared.registry`` for the full list. Owner: Srihith. Change procedure:
coordination/CONTRACTS.md.
"""

SCHEMA_VERSION = (
    "0.7.0"  # 0.2 RLExplanation; 0.3 runtime signals; 0.4 ids allow _-; 0.5 early REPORTING;
    # 0.7 security standards + incidents (0.6 is reserved for intelligence memory, PR #39)
)
