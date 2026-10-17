"""Evidence-backed security standards support.

* ``catalog``  - pinned, checksum-verified framework identifiers (offline).
* ``cvss4``    - CVSS v4.0 scoring ported from FIRST's reference calculator.
* ``cvss_assess`` - evidence-to-metric derivation producing ``CVSSAssessment`` records.
* ``mapping``  - validation of proposed ATT&CK / D3FEND / CWE mappings.
* ``incident`` - NIST SP 800-61r3 incident lifecycle with deterministic approval gates.
* ``owasp_llm`` - the OWASP LLM Top 10 (2025) coverage matrix for this platform.

Nothing here calls a model or the network. Identifiers, scores and lifecycle decisions
are computed by deterministic code from catalog data and recorded evidence.
"""
