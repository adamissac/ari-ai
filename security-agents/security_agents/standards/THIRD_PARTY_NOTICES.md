# Third-party notices for standards reference data

The files in `data/` are compact indexes derived from the primary sources below.
They hold identifiers, titles, versions and a small number of numeric constants.
Retrieval URLs, dates and sha256 digests are in `data/PROVENANCE.json`. License
terms were read from each source on 2026-10-17.

Nothing in this repository is certified by, endorsed by or affiliated with any of
these organizations. The platform's outputs are described as "mapped to" or
"aligned with" these standards, never as compliant or certified.

## MITRE CWE (version 4.20)

Source: https://cwe.mitre.org/data/xml/cwec_latest.xml.zip
Terms: https://cwe.mitre.org/about/termsofuse.html

Copyright © 2006–2026, The MITRE Corporation. CWE, CWSS, CWRAF, and the CWE logo
are trademarks of The MITRE Corporation.

CWE™ is free to use by any organization or individual for any research,
development, and/or commercial purposes, per these CWE Terms of Use. Accordingly,
The MITRE Corporation hereby grants you a non-exclusive, royalty-free license to
use CWE for research, development, and commercial purposes. Any copy you make for
such purposes is authorized on the condition that you reproduce MITRE's copyright
designation and this license in any such copy. CWE is a trademark of The MITRE
Corporation.

## MITRE ATT&CK Enterprise (version 20.0)

Source: https://github.com/mitre-attack/attack-stix-data
Terms: https://attack.mitre.org/resources/legal-and-branding/terms-of-use/

The MITRE Corporation (MITRE) hereby grants you a non-exclusive, royalty-free
license to use ATT&CK® for research, development, and commercial purposes. Any
copy you make for such purposes is authorized provided that you reproduce MITRE's
copyright designation and this license in any such copy.

"© 2026 The MITRE Corporation. This work is reproduced and distributed with the
permission of The MITRE Corporation."

MITRE does not claim ATT&CK enumerates all possibilities for the types of actions
and behaviors documented as part of its adversary model and framework of
techniques. Using the information contained within ATT&CK to address or cover full
categories of techniques will not guarantee full defensive coverage as there may
be undisclosed techniques or variations on existing techniques not documented by
ATT&CK.

## MITRE D3FEND (version 1.6.0)

Source: https://d3fend.mitre.org/ontologies/d3fend.json

License: MIT, as declared by `dcterms:license` in the D3FEND ontology. The D3FEND
legal page returned 404 when retrieved, so the license is taken from the ontology
itself. D3FEND™ is a trademark of The MITRE Corporation.

## OWASP API Security Top 10 (2023 edition)

Source: https://github.com/OWASP/API-Security
License: Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0),
https://creativecommons.org/licenses/by-sa/4.0/

Attribution: OWASP API Security Top 10 2023, by the OWASP API Security Project.
Only the ten category identifiers and their titles are stored, verbatim and
unmodified. The CWE to OWASP category table in `mapping.py` is this repository's
own project mapping and is not part of the OWASP work.

## OWASP Top 10 for LLM Applications (2025 edition)

Source: https://genai.owasp.org/llm-top-10/
License: Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0),
https://creativecommons.org/licenses/by-sa/4.0/

Attribution: OWASP Top 10 for LLM Applications 2025, by the OWASP GenAI Security
Project. Only the ten risk identifiers and their titles are stored, verbatim and
unmodified.

## CVSS v3.1

Source: https://www.first.org/cvss/v3.1/specification-document

CVSS is owned by FIRST and used by permission. FIRST requires that anyone who
publishes CVSS scores follows the specification and publishes both the score and
the vector. This platform always records the vector next to every score it
computes, and labels every score as a base score only.

## CVSS v3.1 test vectors from the NVD

Source: https://services.nvd.nist.gov/rest/json/cves/2.0

Only CVE identifiers, CVSS v3.1 vector strings and base scores are stored, as test
data for the calculator. Each record names the organization that scored it.
UNVERIFIED: the NVD terms of use page returned a Cloudflare challenge when
retrieved, so its terms have not been read.

## NIST SP 800-115

Source: https://csrc.nist.gov/pubs/sp/800/115/final
Terms: https://www.nist.gov/copyrights-disclaimers

With the exception of material marked as copyrighted, information presented on
NIST sites is considered public information and may be distributed or copied;
appropriate credit is requested. Only the publication status, title and section
headings are stored.
