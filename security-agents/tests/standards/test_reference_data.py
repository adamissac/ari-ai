from __future__ import annotations

import hashlib
import json

import pytest

from security_agents.standards import registry

pytestmark = pytest.mark.standards


def test_every_index_has_provenance_with_source_url_version_date_and_hash():
    sources = registry.provenance()["sources"]
    assert set(sources) == set(registry.INDEX_NAMES)
    for name, entry in sources.items():
        assert entry["version"], name
        assert entry["retrieved_at"].endswith("Z"), name
        assert entry["downloads"], name
        for download in entry["downloads"]:
            assert download["url"].startswith("https://"), (name, download["url"])
            assert len(download["sha256"]) == 64, name
            assert download["bytes"] > 0, name
        assert entry["license_note"], name


def test_pinned_files_match_their_recorded_hashes():
    for name in registry.INDEX_NAMES:
        entry = registry.provenance()["sources"][name]
        body = (registry.DATA_DIR / entry["file"]).read_bytes()
        assert hashlib.sha256(body).hexdigest() == entry["file_sha256"], name


def test_tampered_index_fails_closed(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    for path in registry.DATA_DIR.iterdir():
        (data / path.name).write_bytes(path.read_bytes())
    cwe = json.loads((data / "cwe.json").read_text())
    cwe["weaknesses"]["CWE-99999"] = {"name": "invented", "abstraction": "Base", "status": "Draft", "mapping_usage": "Allowed"}
    (data / "cwe.json").write_text(json.dumps(cwe))
    monkeypatch.setattr(registry, "DATA_DIR", data)
    monkeypatch.setattr(registry, "PROVENANCE_FILE", data / "PROVENANCE.json")
    registry.provenance.cache_clear()
    registry.load.cache_clear()
    try:
        with pytest.raises(registry.IntegrityError, match="does not match the pinned"):
            registry.load("cwe")
    finally:
        registry.provenance.cache_clear()
        registry.load.cache_clear()


def test_no_index_is_marked_unverified():
    assert registry.unverified() == {}


@pytest.mark.parametrize(
    "name,version",
    [
        ("cwe", "4.20"),
        ("attack_enterprise", "20.0"),
        ("d3fend", "1.6.0"),
        ("owasp_api", "2023"),
        ("owasp_llm", "2025"),
        ("cvss31", "3.1"),
    ],
)
def test_pinned_editions(name, version):
    assert registry.version(name) == version


def test_owasp_lists_are_complete():
    api = registry.load("owasp_api")["categories"]
    llm = registry.load("owasp_llm")["risks"]
    assert sorted(api) == sorted(f"API{n}:2023" for n in range(1, 11))
    assert sorted(llm) == sorted(f"LLM{n:02d}:2025" for n in range(1, 11))
    assert all(title and len(title) < 80 for title in [*api.values(), *llm.values()])


def test_cwe_index_carries_mitre_mapping_usage():
    weaknesses = registry.load("cwe")["weaknesses"]
    usages = {record["mapping_usage"] for record in weaknesses.values()}
    assert {"Allowed", "Allowed-with-Review", "Discouraged", "Prohibited"} <= usages
    assert weaknesses["CWE-639"]["mapping_usage"] == "Allowed"


def test_nist_sp_800_115_status_and_headings_are_pinned():
    data = registry.load("nist_sp_800_115")
    assert data["status_on_csrc"] == "Final"
    assert data["date_published"] == "September 2008"
    assert [s["section"] for s in data["planning_sections"]] == [f"6.{n}" for n in range(1, 8)]
    sections = [s["section"] for s in data["roe_template_sections"]]
    assert sections[0] == "1" and sections[-1] == "7"
    assert "5.3" in sections and len(sections) == 21


def test_agents_and_tests_never_import_the_refresh_module():
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[2] / "security_agents"
    offenders = [
        str(path.relative_to(root))
        for path in root.rglob("*.py")
        if path.name != "refresh.py" and "standards.refresh" in path.read_text(encoding="utf-8")
    ]
    assert offenders == []


def test_standards_package_has_no_network_client_outside_refresh():
    import ast
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[2] / "security_agents" / "standards"
    banned = {"urllib", "httpx", "requests", "socket", "http", "aiohttp", "anthropic"}
    for path in root.glob("*.py"):
        if path.name == "refresh.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                names = [node.module]
            for name in names:
                assert name.split(".")[0] not in banned, (path.name, name)
