# Third-party standards data and scoring

Reviewed 2026-10-17. Project code remains proprietary; upstream content retains
its own terms. Vendoring for research, development and commercial use is
permitted by the MITRE terms subject to reproducing copyright and license
notices. Notices are retained in `standards/standards/data/LICENSE-*.txt`.
This is an engineering attribution record, not certification or legal advice.

| Source | Verified pin | Official source / terms | Decision |
|---|---|---|---|
| MITRE ATT&CK Enterprise | 20.0 | [data](https://github.com/mitre-attack/attack-stix-data), [terms](https://attack.mitre.org/resources/terms-of-use/) | Vendor normalized identifiers, labels and source hashes; exclude revoked/deprecated techniques from runtime index. |
| MITRE D3FEND | 1.6.0 | [ontology and mapping downloads](https://d3fend.mitre.org/resources/ontology/), [terms](https://d3fend.mitre.org/tou/) | Vendor normalized technique records and official inferred relationships. Preserve full terms including third-party notices. |
| MITRE CWE | 4.20 | [downloads](https://cwe.mitre.org/data/downloads.html), [terms](https://cwe.mitre.org/about/termsofuse.html) | Vendor normalized weaknesses, categories, views and source hashes; classifications must check kind/status. |
| MITRE CAPEC | 3.9 | [XML](https://capec.mitre.org/data/xml/capec_latest.xml), [terms](https://capec.mitre.org/about/termsofuse.html) | Vendor normalized patterns and official relationships with source hashes. |
| OWASP LLM Top 10 | 2025 | [published list](https://genai.owasp.org/llm-top-10/), [license](https://github.com/OWASP/www-project-top-10-for-large-language-model-applications#license) | CC BY-SA 4.0; retain only identifiers/titles, attribute OWASP; no risk descriptions copied. Normalized OWASP file is distributed under CC BY-SA 4.0. |
| FIRST calculator implementation | commit `c5b0d409ae9f57c44264c6ce5f27d89298e1d32a` | [implementation and license](https://github.com/FIRSTdotorg/cvss-v4-calculator/tree/c5b0d409ae9f57c44264c6ce5f27d89298e1d32a) | BSD-2-Clause; canonical Python port and normalized tables reused from Alan’s standards branch, with upstream copyright/license preserved. |
| FIRST CVSS | 4.0 | [specification](https://www.first.org/cvss/v4.0/specification-document) | Use standard via reference implementation, no specification text vendored. Attribute FIRST; no endorsement claimed. |
| NIST SP 800-61 | Rev. 3, April 2025 | [publication](https://csrc.nist.gov/pubs/sp/800/61/r3/final) | Reference lifecycle guidance; no publication text vendored in this package. |

MITRE attribution: © 2026 The MITRE Corporation. This work is reproduced and
distributed with the permission of The MITRE Corporation. ATT&CK®, D3FEND™,
CWE™ and CAPEC™ are MITRE marks; no endorsement is implied.
OWASP attribution: OWASP Top 10 for Large Language Model Applications, 2025,
OWASP Foundation and project contributors, CC BY-SA 4.0; normalization extracts
IDs and titles only. CVSS is owned by FIRST and used by permission.

Exact file hashes, source URLs and versions are recorded in the machine-readable
`standards/standards/data/MANIFEST.json`. Manifest upstream hashes cover the fetched original bytes; normalized indexes
are derived data, not model-generated classifications. Original downloads are
not distributed. `standards/scripts/build_subsets.py` records reproducible extraction.

The D3FEND full mapping download contains ontology-inferred relationships across
frameworks. Runtime extraction includes only ATT&CK techniques that resolve in
the pinned Enterprise catalog and defensive IDs that resolve in D3FEND. This
relationship is a candidate mapping, not demonstrated defensive effectiveness.

## OWASP LLM Top 10 2026 (current release; 2025 retained)

The [official 2026 release announcement](https://genai.owasp.org/2026/09/01/owasp-genai-security-project-unveils-2026-top-10-for-llm-applications-new-agent-control-standard-and-sponsors-as-community-tops-30000-members/)
was checked on 2026-10-17. New normalized data in `owasp-llm-2026.json` derives
from [official final Markdown](https://github.com/GenAI-Security-Project/GenAI-LLM-Top10/tree/9253e38ade58e959b531c0c5c9a4842272c9cd0e/2026/final),
pinned to commit `9253e38ade58e959b531c0c5c9a4842272c9cd0e`. All ten upstream
URLs and SHA-256 values, normalized-file SHA-256, version, and license are in
`MANIFEST.json`. The extraction is repeatable using `build_subsets.py`.

The [repository license declaration](https://github.com/GenAI-Security-Project/GenAI-LLM-Top10/blob/9253e38ade58e959b531c0c5c9a4842272c9cd0e/README.md#license)
specifies CC BY-SA 4.0. Attribution: OWASP GenAI Security Project and contributors,
Top 10 for LLM Applications 2026. The derived file is CC BY-SA 4.0; changes extract
identifiers and titles only, adding source provenance, without copying risk text.
Historical 2025 identifiers retain their original meanings and are not relabeled.
