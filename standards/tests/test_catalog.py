"""Pinned catalogs: integrity, versions, identifier lookups (no network)."""

from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest

from standards import catalog, mapping
from standards.catalog import CatalogIntegrityError, UnknownIdentifier

DATA = Path(catalog.__file__).parent / "data"


def _clear() -> None:
    catalog.manifest.cache_clear()
    catalog.load_json.cache_clear()
    mapping._rules.cache_clear()


@pytest.fixture
def data_copy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    root = tmp_path / "data"
    shutil.copytree(DATA, root)
    monkeypatch.setattr(catalog, "_data_root", lambda: root)
    _clear()
    yield root
    _clear()


def rewrite(root: Path, name: str, data: object, *, update_manifest: bool) -> None:
    raw = json.dumps(data, indent=1, sort_keys=True).encode()
    (root / name).write_bytes(raw)
    if update_manifest:
        man = json.loads((root / "MANIFEST.json").read_text())
        man["files"][name]["sha256"] = hashlib.sha256(raw).hexdigest()
        if isinstance(data, dict) and "version" in data:
            man["files"][name]["version"] = str(data["version"])
        (root / "MANIFEST.json").write_text(json.dumps(man, indent=1, sort_keys=True))
    _clear()


def test_manifest_checksums_match() -> None:
    hashes = catalog.verify_all()
    files = catalog.manifest()["files"]
    assert set(hashes) == set(files)
    for name, meta in files.items():
        assert hashlib.sha256((DATA / name).read_bytes()).hexdigest() == meta["sha256"]
        assert meta.get("version") is not None
        if "curated" not in meta:
            assert meta["upstream"] and all(
                u["url"].startswith("https://") and len(u["sha256"]) == 64 for u in meta["upstream"]
            )


def test_every_data_file_is_listed_in_the_manifest() -> None:
    on_disk = {
        p.relative_to(DATA).as_posix() for p in DATA.rglob("*.json") if p.name != "MANIFEST.json"
    }
    assert on_disk == set(catalog.manifest()["files"])


def test_tampered_file_is_refused(data_copy: Path) -> None:
    d3 = json.loads((data_copy / "d3fend.json").read_text())
    d3["techniques"]["D3-FAKE"] = {"name": "Injected", "url": None}
    rewrite(data_copy, "d3fend.json", d3, update_manifest=False)
    with pytest.raises(CatalogIntegrityError):
        catalog.d3fend_technique("D3-NI")
    with pytest.raises(CatalogIntegrityError):
        catalog.load_json("not-listed.json")


def test_pinned_versions() -> None:
    assert catalog.catalog_versions() == {
        "attack": "20.0",
        "d3fend": "1.6.0",
        "cwe": "4.20",
        "capec": "3.9",
        "owasp_llm": "2025",
        "cvss": "4.0",
        "nist_800_61": "Rev. 3",
        "nist_csf": "2.0",
    }


def test_lookups_resolve_status_and_replacements() -> None:
    t = catalog.attack_technique("T1190")
    assert (t.name, t.status, t.catalog_version) == (
        "Exploit Public-Facing Application",
        "active",
        "20.0",
    )
    revoked = catalog.attack_technique("T1002")
    assert (revoked.status, revoked.replaced_by) == ("revoked", "T1560")
    assert catalog.attack_technique("T1026").status == "deprecated"
    assert catalog.d3fend_technique("D3-NI").name == "Network Isolation"
    idor = catalog.cwe("CWE-639")
    assert (idor.detail["kind"], idor.detail["mapping_usage"]) == ("weakness", "Allowed")
    category = catalog.cwe("CWE-840")
    assert (category.detail["kind"], category.detail["mapping_usage"]) == (
        "category",
        "Prohibited",
    )
    assert catalog.cwe("CWE-1").status == "deprecated"
    assert catalog.owasp_llm_ids() == [f"LLM{n:02d}:2025" for n in range(1, 11)]
    assert catalog.nist_csf_function("RS").name


@pytest.mark.parametrize(
    ("framework", "identifier"),
    [
        ("attack", "T9999"),
        ("attack", "T12"),
        ("attack", "t1190"),
        ("d3fend", "D3-NOPE"),
        ("d3fend", "NI"),
        ("cwe", "CWE-99999"),
        ("cwe", "cwe-79"),
        ("cwe", "79"),
        ("owasp_llm", "LLM11:2025"),
        ("owasp_llm", "LLM01:2023"),
        ("nist_csf", "XX"),
    ],
)
def test_unknown_and_malformed_identifiers_raise(framework: str, identifier: str) -> None:
    with pytest.raises(UnknownIdentifier):
        catalog.lookup(framework, identifier)  # type: ignore[arg-type]


def test_capec_chain_is_catalog_data_only() -> None:
    assert catalog.capec_for_cwe("CWE-639") == []
    assert catalog.capec_for_cwe("CWE-284")
