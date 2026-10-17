"""Canonical cross-subsystem contracts (single source of truth, ADR-0004).

Import models from their modules (``from shared.findings import Finding``) or from
``shared.registry`` for the full list. Owner: Srihith. Change procedure:
coordination/CONTRACTS.md.
"""

SCHEMA_VERSION = "0.4.0"  # 0.2.0 RLExplanation; 0.3.0 runtime signals; 0.4.0 ids allow _ and -
