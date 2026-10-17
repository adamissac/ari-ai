# Offline security standards

The canonical catalog and FIRST CVSS v4.0 port are reused from Alan's pushed
`feat/alan/security-standards` implementation rather than duplicating them.
`standards.catalog` lookups return frozen `CatalogEntry` objects with `id`,
`name`, `catalog_version`, `status`, `url`, and framework-specific `detail`.
Unknown identifiers raise `UnknownIdentifier` (`KeyError`). Historical deprecated
and revoked entries remain readable; new mappings must check status. CWE
categories/views remain readable but cannot classify a vulnerability as weaknesses.

`capec_for_cwe`, `attack_for_capec`, and `d3fend_for_attack` return identifier
lists. Cross-framework links are source classifications, not detection claims.
CWE-639 has no official CAPEC chain in the pinned sources, so its link list is
empty. Do not invent a chain to satisfy a demo. `fortify_d3fend` and `rl_d3fend`
return candidate defense `CatalogEntry` lists. Only simulation `isolate` has a
reviewed `D3-NI` rule; generic categories cannot establish implemented controls.

`standards.cvss4.build_vector(metrics)` validates explicit metrics;
`score(vector)` returns a `CVSSResult` with computed score, severity, macrovector
and nomenclature. This is the canonical FIRST calculator port, not an LLM score
and not a second third-party scoring library. `standards.cvss` is a small legacy
base-only adapter forwarding to this same port; it never infers missing metrics
from SeverityFactors prose. Missing metric evidence leaves assessments unscored.

`data/MANIFEST.json` pins normalized data hashes, official upstream URLs/hashes,
versions, and preserved license notices. No runtime catalog network calls exist.
`python -m standards.catalog --check` verifies pinned artifacts offline.
`standards/scripts/build_subsets.py` is an explicit data refresh tool, not a
runtime path. Catalog releases are ATT&CK 20.0, D3FEND 1.6.0, CWE 4.20, CAPEC 3.9,
OWASP LLM 2025, NIST SP 800-61r3 / CSF 2.0, and CVSS 4.0.

Tests execute all 3,047 FIRST JavaScript-generated golden vectors and verify published
examples: 39 of 47 detail scores agree, and all 47 computed scores match the
independent JavaScript oracle. The published page has inconsistent table/detail
scores; tests preserve that fact instead of altering numeric scoring to fit labels.
Run `uv run pytest -q standards/tests` and `uv run ruff check standards`.
See [third-party notices](../docs/THIRD_PARTY_DATA.md) before distribution.
