"""Read-only, offline catalogs of framework identifiers.

Every file under ``standards/data`` is listed in ``MANIFEST.json`` with its SHA-256; a file
whose bytes do not match is refused (``CatalogIntegrityError``), so a hand edit or a
corrupted checkout cannot silently change which identifiers are considered valid.

Lookups return a :class:`CatalogEntry` and raise :class:`UnknownIdentifier` for anything
not in the pinned release. Deprecated/revoked entries *are* returned (so history stays
readable) but carry ``status != "active"``; the mapping validator decides what to do
with them.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from functools import cache
from importlib import resources
from typing import Any, Literal

Framework = Literal["attack", "attack_tactic", "d3fend", "cwe", "capec", "owasp_llm", "nist_csf"]
EntryStatus = Literal["active", "deprecated", "revoked"]


class CatalogIntegrityError(RuntimeError):
    """A vendored data file does not match its pinned SHA-256."""


class UnknownIdentifier(KeyError):
    """The identifier does not exist in the pinned framework release."""


@dataclass(frozen=True)
class CatalogEntry:
    framework: Framework
    id: str
    name: str
    catalog_version: str
    url: str | None
    status: EntryStatus
    replaced_by: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)


def _data_root() -> Any:
    return resources.files("standards") / "data"


@cache
def manifest() -> dict[str, Any]:
    return json.loads((_data_root() / "MANIFEST.json").read_text(encoding="utf-8"))


@cache
def load_json(name: str) -> Any:
    entry = manifest()["files"].get(name)
    if entry is None:
        raise CatalogIntegrityError(f"{name} is not listed in MANIFEST.json")
    raw = (_data_root() / name).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != entry["sha256"]:
        raise CatalogIntegrityError(
            f"{name}: sha256 {digest} does not match MANIFEST {entry['sha256']}"
        )
    return json.loads(raw.decode("utf-8"))


def verify_all() -> dict[str, str]:
    """Load every manifest file, raising on any checksum mismatch. Returns name -> sha256."""
    return {
        name: (load_json(name), meta["sha256"])[1] for name, meta in manifest()["files"].items()
    }


def catalog_versions() -> dict[str, str]:
    return {
        "attack": str(load_json("attack-enterprise.json")["version"]),
        "d3fend": str(load_json("d3fend.json")["version"]),
        "cwe": str(load_json("cwe.json")["version"]),
        "capec": str(load_json("capec.json")["version"]),
        "owasp_llm": str(load_json("owasp-llm.json")["version"]),
        "cvss": "4.0",
        "nist_800_61": str(load_json("nist-sp800-61r3.json")["version"]),
        "nist_csf": str(load_json("nist-sp800-61r3.json")["csf_version"]),
    }


# ------------------------------------------------------------------ normalisation

_ATTACK_RE = re.compile(r"^T\d{4}(\.\d{3})?$")
_TACTIC_RE = re.compile(r"^TA\d{4}$")
_D3_RE = re.compile(r"^D3-[A-Z0-9]+$")
_CWE_RE = re.compile(r"^CWE-\d{1,5}$")
_CAPEC_RE = re.compile(r"^CAPEC-\d{1,5}$")
_OWASP_RE = re.compile(r"^LLM(0[1-9]|10):2025$")


def _check(pattern: re.Pattern[str], value: str, framework: str) -> str:
    if not pattern.match(value):
        raise UnknownIdentifier(f"{value!r} is not a well-formed {framework} identifier")
    return value


# ------------------------------------------------------------------ lookups


def attack_technique(technique_id: str) -> CatalogEntry:
    _check(_ATTACK_RE, technique_id, "ATT&CK technique")
    data = load_json("attack-enterprise.json")
    raw = data["techniques"].get(technique_id)
    if raw is None:
        raise UnknownIdentifier(f"{technique_id} is not in ATT&CK Enterprise v{data['version']}")
    status: EntryStatus = (
        "revoked" if raw["revoked"] else "deprecated" if raw["deprecated"] else "active"
    )
    return CatalogEntry(
        framework="attack",
        id=technique_id,
        name=raw["name"],
        catalog_version=str(data["version"]),
        url=raw["url"],
        status=status,
        replaced_by=raw.get("revoked_by"),
        detail={"tactics": list(raw["tactics"]), "is_subtechnique": raw["is_subtechnique"]},
    )


def attack_tactic(tactic_id: str) -> CatalogEntry:
    _check(_TACTIC_RE, tactic_id, "ATT&CK tactic")
    data = load_json("attack-enterprise.json")
    raw = data["tactics"].get(tactic_id)
    if raw is None:
        raise UnknownIdentifier(f"{tactic_id} is not in ATT&CK Enterprise v{data['version']}")
    return CatalogEntry(
        framework="attack_tactic",
        id=tactic_id,
        name=raw["name"],
        catalog_version=str(data["version"]),
        url=raw["url"],
        status="deprecated" if raw["deprecated"] else "active",
        detail={"shortname": raw["shortname"]},
    )


def attack_tactic_by_shortname(shortname: str) -> CatalogEntry:
    data = load_json("attack-enterprise.json")
    for tid, raw in data["tactics"].items():
        if raw["shortname"] == shortname:
            return attack_tactic(tid)
    raise UnknownIdentifier(f"no ATT&CK tactic with shortname {shortname!r}")


def d3fend_technique(technique_id: str) -> CatalogEntry:
    _check(_D3_RE, technique_id, "D3FEND technique")
    data = load_json("d3fend.json")
    raw = data["techniques"].get(technique_id)
    if raw is None:
        raise UnknownIdentifier(f"{technique_id} is not in D3FEND {data['version']}")
    return CatalogEntry(
        framework="d3fend",
        id=technique_id,
        name=raw["name"],
        catalog_version=str(data["version"]),
        url=raw["url"],
        status="deprecated" if raw["deprecated"] else "active",
        detail={"tactic": raw["tactic"], "parent": raw["parent"]},
    )


def cwe(cwe_id: str) -> CatalogEntry:
    _check(_CWE_RE, cwe_id, "CWE")
    data = load_json("cwe.json")
    raw = data["entries"].get(cwe_id)
    if raw is None:
        raise UnknownIdentifier(f"{cwe_id} is not in CWE {data['version']}")
    status: EntryStatus = "deprecated" if raw["status"] in ("Deprecated", "Obsolete") else "active"
    return CatalogEntry(
        framework="cwe",
        id=cwe_id,
        name=raw["name"],
        catalog_version=str(data["version"]),
        url=raw["url"],
        status=status,
        detail={
            "kind": raw["kind"],
            "cwe_status": raw["status"],
            "mapping_usage": raw["mapping_usage"],
            "abstraction": raw.get("abstraction"),
            "capec": list(raw.get("capec", [])),
        },
    )


def capec(capec_id: str) -> CatalogEntry:
    _check(_CAPEC_RE, capec_id, "CAPEC")
    data = load_json("capec.json")
    raw = data["patterns"].get(capec_id)
    if raw is None:
        raise UnknownIdentifier(f"{capec_id} is not in CAPEC {data['version']}")
    status: EntryStatus = "deprecated" if raw["status"] in ("Deprecated", "Obsolete") else "active"
    return CatalogEntry(
        framework="capec",
        id=capec_id,
        name=raw["name"],
        catalog_version=str(data["version"]),
        url=raw["url"],
        status=status,
        detail={"cwe": list(raw["cwe"]), "attack": list(raw["attack"])},
    )


def owasp_llm(risk_id: str) -> CatalogEntry:
    _check(_OWASP_RE, risk_id, "OWASP LLM Top 10 2025")
    data = load_json("owasp-llm.json")
    raw = data["risks"].get(risk_id)
    if raw is None:  # pragma: no cover - the regex admits exactly the ten ids
        raise UnknownIdentifier(risk_id)
    return CatalogEntry(
        framework="owasp_llm",
        id=risk_id,
        name=raw["name"],
        catalog_version=str(data["version"]),
        url=data["url"],
        status="active",
        detail={"source_file": raw["source_file"], "source_sha256": raw["source_sha256"]},
    )


def owasp_llm_ids() -> list[str]:
    return sorted(load_json("owasp-llm.json")["risks"])


def nist_csf_function(code: str) -> CatalogEntry:
    data = load_json("nist-sp800-61r3.json")
    raw = data["csf_functions"].get(code)
    if raw is None:
        raise UnknownIdentifier(f"{code} is not a NIST CSF {data['csf_version']} function")
    return CatalogEntry(
        framework="nist_csf",
        id=code,
        name=raw["name"],
        catalog_version=str(data["csf_version"]),
        url=data["csf_url"],
        status="active",
        detail={"role_in_800_61r3": raw["role_in_800_61r3"]},
    )


def lookup(framework: Framework, identifier: str) -> CatalogEntry:
    fn = {
        "attack": attack_technique,
        "attack_tactic": attack_tactic,
        "d3fend": d3fend_technique,
        "cwe": cwe,
        "capec": capec,
        "owasp_llm": owasp_llm,
        "nist_csf": nist_csf_function,
    }[framework]
    return fn(identifier)


# ------------------------------------------------------------------ cross-framework links


def capec_for_cwe(cwe_id: str) -> list[str]:
    """CAPEC patterns linked to a CWE, from the union of both catalogs' own relations."""
    linked = set(cwe(cwe_id).detail["capec"])
    for pid, raw in load_json("capec.json")["patterns"].items():
        if cwe_id in raw["cwe"]:
            linked.add(pid)
    return sorted(linked, key=lambda s: int(s.split("-")[1]))


def attack_for_capec(capec_id: str) -> list[str]:
    """ATT&CK ids listed in CAPEC's own taxonomy mappings (may be stale; validate each)."""
    return list(capec(capec_id).detail["attack"])
