from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).parent / "data"
PROVENANCE_FILE = DATA_DIR / "PROVENANCE.json"

INDEX_NAMES = (
    "cwe",
    "attack_enterprise",
    "d3fend",
    "owasp_api",
    "owasp_llm",
    "cvss31",
    "cvss31_vectors",
    "nist_sp_800_115",
)


class IntegrityError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def provenance() -> dict[str, Any]:
    if not PROVENANCE_FILE.is_file():
        raise IntegrityError(f"missing {PROVENANCE_FILE}")
    return json.loads(PROVENANCE_FILE.read_text(encoding="utf-8"))


@lru_cache(maxsize=None)
def load(name: str) -> dict[str, Any]:
    if name not in INDEX_NAMES:
        raise KeyError(f"unknown standards index {name!r}")
    entry = provenance()["sources"].get(name)
    if entry is None:
        raise IntegrityError(f"{name} has no provenance entry")
    path = DATA_DIR / entry["file"]
    body = path.read_bytes()
    digest = hashlib.sha256(body).hexdigest()
    if digest != entry["file_sha256"]:
        raise IntegrityError(
            f"{path.name} sha256 {digest} does not match the pinned {entry['file_sha256']}"
        )
    return json.loads(body)


def version(name: str) -> str:
    return str(provenance()["sources"][name]["version"])


def unverified() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {
        name: list(entry.get("unverified", []))
        for name, entry in provenance()["sources"].items()
        if entry.get("unverified")
    }
    for name, terms in provenance().get("licenses", {}).items():
        if not terms.get("verified"):
            out.setdefault(name, []).append(f"license terms not verified: {terms.get('license', '')}")
    return out


def licenses() -> dict[str, dict[str, Any]]:
    return dict(provenance().get("licenses", {}))


def summary() -> list[dict[str, Any]]:
    rows = []
    counts = {
        "cwe": lambda d: len(d["weaknesses"]) + len(d["categories"]),
        "attack_enterprise": lambda d: len(d["techniques"]),
        "d3fend": lambda d: len(d["techniques"]),
        "owasp_api": lambda d: len(d["categories"]),
        "owasp_llm": lambda d: len(d["risks"]),
        "cvss31": lambda d: sum(len(v) for v in d["weights"].values()),
        "cvss31_vectors": lambda d: len(d["vectors"]),
        "nist_sp_800_115": lambda d: 1,
    }
    for name in INDEX_NAMES:
        entry = provenance()["sources"][name]
        data = load(name)
        rows.append(
            {
                "name": name,
                "standard": data.get("standard", name),
                "version": entry["version"],
                "identifiers": counts[name](data),
                "retrieved_at": entry["retrieved_at"],
                "unverified": list(entry.get("unverified", [])),
            }
        )
    return rows
