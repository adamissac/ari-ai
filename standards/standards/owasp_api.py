from __future__ import annotations

import re
from dataclasses import dataclass

from .catalog import CatalogEntry, UnknownIdentifier, cwe, load_json

OWASP_API_RE = re.compile(r"^API\d{1,2}:\d{4}$")
PERMITTED_USAGE = frozenset({"Allowed", "Allowed-with-Review"})


@dataclass(frozen=True)
class OwaspApiTag:
    category: str | None
    title: str | None
    edition: str
    kind: str
    note: str


def owasp_api(category_id: str) -> CatalogEntry:
    if not OWASP_API_RE.match(category_id):
        raise UnknownIdentifier(f"{category_id!r} is not of the form APIn:YYYY")
    data = load_json("owasp-api-2023.json")
    raw = data["categories"].get(category_id)
    if raw is None:
        raise UnknownIdentifier(
            f"{category_id} is not in OWASP API Security Top 10 {data['version']}"
        )
    return CatalogEntry(
        framework="owasp_api",
        id=category_id,
        name=raw["name"],
        catalog_version=str(data["version"]),
        url="https://owasp.org/API-Security/editions/2023/en/0x11-t10/",
        status="active",
        detail={"framework": "owasp_api"},
    )


def project_mapping() -> dict[str, list[str]]:
    return dict(load_json("rules/cwe_owasp_api.json")["categories"])


def unmapped_reasons() -> dict[str, str]:
    return dict(load_json("rules/cwe_owasp_api.json")["unmapped"])


def _reverse() -> dict[str, str]:
    reverse: dict[str, str] = {}
    for category, cwes in project_mapping().items():
        for identifier in cwes:
            if identifier in reverse:
                raise ValueError(
                    f"{identifier} is mapped to both {reverse[identifier]} and {category}"
                )
            reverse[identifier] = category
    return reverse


def mapping_problems() -> list[str]:
    problems: list[str] = []
    for category, cwes in project_mapping().items():
        try:
            owasp_api(category)
        except UnknownIdentifier as error:
            problems.append(str(error))
        for identifier in cwes:
            try:
                entry = cwe(identifier)
            except UnknownIdentifier as error:
                problems.append(str(error))
                continue
            if entry.detail.get("kind") != "weakness":
                problems.append(f"{identifier} is a CWE {entry.detail.get('kind')}, not a weakness")
            if entry.status != "active":
                problems.append(f"{identifier} is {entry.status}")
            if entry.detail.get("mapping_usage") not in PERMITTED_USAGE:
                problems.append(
                    f"{identifier} has MITRE mapping usage {entry.detail.get('mapping_usage')}"
                )
    try:
        _reverse()
    except ValueError as error:
        problems.append(str(error))
    return problems


def owasp_api_tag(cwe_id: str) -> OwaspApiTag:
    cwe(cwe_id)
    edition = str(load_json("owasp-api-2023.json")["version"])
    category = _reverse().get(cwe_id)
    if category is None:
        return OwaspApiTag(
            category=None,
            title=None,
            edition=edition,
            kind="project mapping",
            note="no applicable OWASP API Security Top 10 category in the project mapping",
        )
    return OwaspApiTag(
        category=category,
        title=owasp_api(category).name,
        edition=edition,
        kind="project mapping",
        note="project mapping authored in this repository, not an official OWASP or MITRE mapping",
    )
