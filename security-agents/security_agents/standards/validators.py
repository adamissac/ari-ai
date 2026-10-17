from __future__ import annotations

import re
from dataclasses import dataclass

from .registry import load

CWE_PATTERN = re.compile(r"^CWE-\d{1,5}$")
ATTACK_PATTERN = re.compile(r"^T\d{4}(\.\d{3})?$")
D3FEND_PATTERN = re.compile(r"^D3-[A-Z0-9]{1,12}$")
OWASP_API_PATTERN = re.compile(r"^API\d{1,2}:\d{4}$")
OWASP_LLM_PATTERN = re.compile(r"^LLM\d{2}:\d{4}$")

CWE_REJECTED_USAGE = frozenset({"Prohibited", "Discouraged"})
CWE_REVIEW_USAGE = frozenset({"Allowed-with-Review"})


class StandardsViolation(ValueError):
    def __init__(self, standard: str, identifier: str, reason: str) -> None:
        super().__init__(f"{standard} {identifier!r}: {reason}")
        self.standard = standard
        self.identifier = identifier
        self.reason = reason


@dataclass(frozen=True)
class CweRecord:
    identifier: str
    name: str
    kind: str
    abstraction: str
    mapping_usage: str
    needs_review: bool
    catalog_version: str


@dataclass(frozen=True)
class AttackRecord:
    identifier: str
    name: str
    tactics: tuple[str, ...]
    sub_technique: bool
    version: str


@dataclass(frozen=True)
class D3fendRecord:
    identifier: str
    label: str
    version: str


@dataclass(frozen=True)
class OwaspRecord:
    identifier: str
    title: str
    edition: str


def validate_cwe(identifier: str) -> CweRecord:
    value = str(identifier).strip()
    if not CWE_PATTERN.match(value):
        raise StandardsViolation("CWE", value, "not of the form CWE-<number>")
    data = load("cwe")
    record = data["weaknesses"].get(value)
    kind = "weakness"
    if record is None:
        record = data["categories"].get(value)
        kind = "category"
    if record is None:
        raise StandardsViolation(
            "CWE", value, f"not in the pinned CWE {data['version']} catalog"
        )
    if record.get("status") == "Deprecated":
        raise StandardsViolation("CWE", value, "is deprecated in the CWE catalog")
    usage = record.get("mapping_usage", "")
    if usage in CWE_REJECTED_USAGE:
        raise StandardsViolation(
            "CWE",
            value,
            f"MITRE mapping usage is {usage!r}; choose a more specific weakness whose usage is Allowed",
        )
    return CweRecord(
        identifier=value,
        name=record.get("name", ""),
        kind=kind,
        abstraction=record.get("abstraction", "Category" if kind == "category" else ""),
        mapping_usage=usage,
        needs_review=usage in CWE_REVIEW_USAGE,
        catalog_version=str(data["version"]),
    )


def validate_attack_technique(identifier: str) -> AttackRecord:
    value = str(identifier).strip()
    if not ATTACK_PATTERN.match(value):
        raise StandardsViolation("ATT&CK", value, "not of the form T<4 digits> or T<4 digits>.<3 digits>")
    data = load("attack_enterprise")
    record = data["techniques"].get(value)
    if record is None:
        raise StandardsViolation(
            "ATT&CK", value, f"not in the pinned Enterprise ATT&CK v{data['version']}"
        )
    if record.get("revoked"):
        raise StandardsViolation("ATT&CK", value, "is revoked in Enterprise ATT&CK")
    if record.get("deprecated"):
        raise StandardsViolation("ATT&CK", value, "is deprecated in Enterprise ATT&CK")
    return AttackRecord(
        identifier=value,
        name=record.get("name", ""),
        tactics=tuple(record.get("tactics", [])),
        sub_technique=bool(record.get("sub_technique")),
        version=str(data["version"]),
    )


def validate_d3fend(identifier: str) -> D3fendRecord:
    value = str(identifier).strip()
    if not D3FEND_PATTERN.match(value):
        raise StandardsViolation("D3FEND", value, "not of the form D3-<CODE>")
    data = load("d3fend")
    record = data["techniques"].get(value)
    if record is None:
        raise StandardsViolation("D3FEND", value, f"not in the pinned D3FEND {data['version']}")
    return D3fendRecord(identifier=value, label=record.get("label", ""), version=str(data["version"]))


def validate_owasp_api(identifier: str) -> OwaspRecord:
    value = str(identifier).strip()
    if not OWASP_API_PATTERN.match(value):
        raise StandardsViolation("OWASP API Top 10", value, "not of the form APIn:YYYY")
    data = load("owasp_api")
    title = data["categories"].get(value)
    if title is None:
        raise StandardsViolation(
            "OWASP API Top 10", value, f"not in the pinned {data['version']} edition"
        )
    return OwaspRecord(identifier=value, title=title, edition=str(data["version"]))


def validate_owasp_llm(identifier: str) -> OwaspRecord:
    value = str(identifier).strip()
    if not OWASP_LLM_PATTERN.match(value):
        raise StandardsViolation("OWASP LLM Top 10", value, "not of the form LLMnn:YYYY")
    data = load("owasp_llm")
    title = data["risks"].get(value)
    if title is None:
        raise StandardsViolation(
            "OWASP LLM Top 10", value, f"not in the pinned {data['version']} edition"
        )
    return OwaspRecord(identifier=value, title=title, edition=str(data["version"]))


def cwe_field(value: str) -> str:
    validate_cwe(value)
    return value


def optional_attack_field(value: str | None) -> str | None:
    if value is None or value == "":
        return None
    validate_attack_technique(value)
    return value


def optional_d3fend_field(value: str | None) -> str | None:
    if value is None or value == "":
        return None
    validate_d3fend(value)
    return value
