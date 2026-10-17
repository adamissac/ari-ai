from __future__ import annotations

from dataclasses import dataclass

from .registry import load
from .validators import validate_cwe, validate_owasp_api

MAPPING_KIND = "project mapping"
MAPPING_NOTE = (
    "Project mapping authored by this repository, not an official OWASP or MITRE mapping. "
    "Every CWE listed is validated against the pinned CWE catalog and uses only identifiers whose "
    "MITRE mapping usage is Allowed or Allowed-with-Review."
)

CWE_TO_OWASP_API_2023: dict[str, tuple[str, ...]] = {
    "API1:2023": ("CWE-639", "CWE-566"),
    "API2:2023": ("CWE-306", "CWE-307", "CWE-798", "CWE-1390", "CWE-522"),
    "API3:2023": ("CWE-213", "CWE-915", "CWE-1321"),
    "API4:2023": ("CWE-770", "CWE-1333"),
    "API5:2023": ("CWE-862", "CWE-863"),
    "API6:2023": ("CWE-799", "CWE-837", "CWE-841"),
    "API7:2023": ("CWE-918",),
    "API8:2023": ("CWE-942", "CWE-1004", "CWE-614", "CWE-489", "CWE-1188", "CWE-319"),
    "API9:2023": (),
    "API10:2023": ("CWE-829", "CWE-1357", "CWE-502"),
}

UNMAPPED_REASONS: dict[str, str] = {
    "API9:2023": "No CWE with Allowed mapping usage describes inventory management; left unmapped on purpose.",
}


@dataclass(frozen=True)
class OwaspTag:
    category: str | None
    title: str | None
    edition: str
    kind: str
    note: str


def _reverse() -> dict[str, str]:
    reverse: dict[str, str] = {}
    for category, cwes in CWE_TO_OWASP_API_2023.items():
        for cwe in cwes:
            if cwe in reverse:
                raise ValueError(f"{cwe} is mapped to both {reverse[cwe]} and {category}")
            reverse[cwe] = category
    return reverse


def owasp_api_tag(cwe_identifier: str) -> OwaspTag:
    validate_cwe(cwe_identifier)
    edition = str(load("owasp_api")["version"])
    category = _reverse().get(cwe_identifier)
    if category is None:
        return OwaspTag(
            category=None,
            title=None,
            edition=edition,
            kind=MAPPING_KIND,
            note="no applicable OWASP API Security Top 10 category in the project mapping",
        )
    record = validate_owasp_api(category)
    return OwaspTag(
        category=category, title=record.title, edition=edition, kind=MAPPING_KIND, note=MAPPING_NOTE
    )


def mapped_cwes() -> list[str]:
    return sorted(_reverse())
