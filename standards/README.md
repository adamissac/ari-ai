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

## OWASP 2026 and historical 2025 IDs

The current OWASP LLM Top 10 2026 release is also pinned, from official repository
commit `9253e38ade58e959b531c0c5c9a4842272c9cd0e`. `owasp_llm("LLM03:2026")`
resolves Excessive Agency; the historical `LLM03:2025` still resolves Supply Chain.
IDs must always retain their year because ordering and terminology changed.
`owasp_llm_ids(version="2026")` lists current IDs; the default remains `"2025"`
for compatibility. `catalog_versions()["owasp_llm2026"]` reports the new release.
`build_subsets.py` pins every 2026 Markdown source hash and parses only headings.
The normalized catalog contains identifiers, titles, and provenance, without risk
prose. Current release coverage is distinct from the historical 2025 matrix.

## Additional runtime reference catalogs

CVSS v3.1 base scoring (`standards.cvss31`), OWASP API Security 2023 categories
(`standards.owasp_api`), and NIST SP 800-115 planning/ROE headings now use the
canonical integrity-checked catalog store. The v3.1 calculator is separate from
CVSS 4.0 and accepts only explicit base metrics. **Runtime severity uses CVSS v3.1**
(ADR-0012): Trace's v3.1 base metrics are scored by `standards.cvss31` and that rating sets
`SeverityAssessment.level`. CVSS 4.0 is reported **alongside and never sets the level**:
Trace's provisional `SeverityAssessment.cvss` and the fact-derived `Finding.standards.cvss`
(`standards.cvss_assess`). Both are base scores only, not a vulnerability-management rating. CWE-to-OWASP API associations are labelled project
mappings. `scripts/build_additional.py` records source hashes for explicit refresh;
it never runs on the runtime path. NVD vector fixture terms remain labelled
unverified in the manifest; no new redistribution approval is claimed.
