from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from html import unescape
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).parent / "data"
PROVENANCE_FILE = DATA_DIR / "PROVENANCE.json"
USER_AGENT = "hackatl-agentic-security standards refresh (security-agents)"
TIMEOUT = 180

SOURCES: dict[str, dict[str, str]] = {
    "cwe": {
        "url": "https://cwe.mitre.org/data/xml/cwec_latest.xml.zip",
        "landing": "https://cwe.mitre.org/data/downloads.html",
        "license": "CWE is free to use with attribution; see https://cwe.mitre.org/about/termsofuse.html",
    },
    "attack_enterprise": {
        "url": "https://raw.githubusercontent.com/mitre-attack/attack-stix-data/master/index.json",
        "landing": "https://attack.mitre.org/resources/legal-and-branding/terms-of-use/",
        "license": "ATT&CK is free to use with attribution; see the MITRE ATT&CK Terms of Use",
    },
    "d3fend": {
        "url": "https://d3fend.mitre.org/ontologies/d3fend.json",
        "landing": "https://d3fend.mitre.org/resources/legal/",
        "license": "declared in the ontology as dcterms:license",
    },
    "owasp_api": {
        "url": "https://raw.githubusercontent.com/OWASP/API-Security/master/editions/2023/en/0x11-t10.md",
        "landing": "https://owasp.org/API-Security/",
        "license": "see the OWASP API Security project repository LICENSE",
    },
    "owasp_llm": {
        "url": "https://genai.owasp.org/llm-top-10/",
        "landing": "https://genai.owasp.org/llm-top-10/",
        "license": "see the OWASP GenAI Security Project site terms",
    },
    "cvss31": {
        "url": "https://www.first.org/cvss/v3.1/specification-document",
        "landing": "https://www.first.org/cvss/",
        "license": "CVSS is owned by FIRST; free to use with attribution",
    },
    "cvss31_vectors": {
        "url": "https://services.nvd.nist.gov/rest/json/cves/2.0",
        "landing": "https://nvd.nist.gov/developers/vulnerabilities",
        "license": "NVD data is public domain; see https://nvd.nist.gov/general/FAQ-Sections/General-FAQs",
    },
    "nist_sp_800_115": {
        "url": "https://csrc.nist.gov/pubs/sp/800/115/final",
        "pdf": "https://nvlpubs.nist.gov/nistpubs/Legacy/SP/nistspecialpublication800-115.pdf",
        "landing": "https://csrc.nist.gov/pubs/sp/800/115/final",
        "license": "NIST publications are public domain within the United States",
    },
}


@dataclass
class Fetched:
    url: str
    body: bytes
    sha256: str = ""
    retrieved_at: str = ""

    def __post_init__(self) -> None:
        self.sha256 = hashlib.sha256(self.body).hexdigest()
        self.retrieved_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class Built:
    name: str
    payload: dict[str, Any]
    version: str
    version_source: str
    sources: list[Fetched] = field(default_factory=list)
    license_note: str = ""
    notes: list[str] = field(default_factory=list)


def fetch(url: str) -> Fetched:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return Fetched(url=url, body=response.read())


def text_of(fetched: Fetched) -> str:
    raw = fetched.body.decode("utf-8", errors="replace")
    raw = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", raw, flags=re.S)
    raw = re.sub(r"<[^>]+>", " ", raw)
    return re.sub(r"[ \t]+", " ", unescape(raw))


def build_cwe() -> Built:
    fetched = fetch(SOURCES["cwe"]["url"])
    with zipfile.ZipFile(io.BytesIO(fetched.body)) as archive:
        name = next(n for n in archive.namelist() if n.endswith(".xml"))
        xml_bytes = archive.read(name)
    root = ET.fromstring(xml_bytes)
    namespace = root.tag.split("}")[0].strip("{")
    version = root.attrib["Version"]
    catalog_date = root.attrib.get("Date", "")
    def usage_of(element: ET.Element) -> str:
        notes = element.find(f"{{{namespace}}}Mapping_Notes")
        usage = notes.find(f"{{{namespace}}}Usage") if notes is not None else None
        return (usage.text or "").strip() if usage is not None else ""

    weaknesses: dict[str, dict[str, str]] = {}
    for element in root.iter(f"{{{namespace}}}Weakness"):
        identifier = element.attrib.get("ID")
        if not identifier:
            continue
        weaknesses[f"CWE-{identifier}"] = {
            "name": element.attrib.get("Name", ""),
            "abstraction": element.attrib.get("Abstraction", ""),
            "status": element.attrib.get("Status", ""),
            "mapping_usage": usage_of(element),
        }
    categories: dict[str, dict[str, str]] = {}
    for element in root.iter(f"{{{namespace}}}Category"):
        identifier = element.attrib.get("ID")
        if identifier:
            categories[f"CWE-{identifier}"] = {
                "name": element.attrib.get("Name", ""),
                "status": element.attrib.get("Status", ""),
                "mapping_usage": usage_of(element),
            }
    payload = {
        "standard": "MITRE CWE",
        "version": version,
        "catalog_date": catalog_date,
        "archive_member": name,
        "archive_member_sha256": hashlib.sha256(xml_bytes).hexdigest(),
        "weakness_count": len(weaknesses),
        "category_count": len(categories),
        "weaknesses": dict(sorted(weaknesses.items(), key=_cwe_sort)),
        "categories": dict(sorted(categories.items(), key=_cwe_sort)),
    }
    return Built(
        name="cwe",
        payload=payload,
        version=version,
        version_source="Weakness_Catalog/@Version in cwec_latest.xml",
        sources=[fetched],
        license_note=SOURCES["cwe"]["license"],
        notes=[f"catalog date {catalog_date}"],
    )


def _cwe_sort(item: tuple[str, Any]) -> tuple[int, str]:
    key = item[0]
    digits = key.split("-", 1)[1]
    return (int(digits) if digits.isdigit() else 10**9, key)


def build_attack_enterprise() -> Built:
    index = fetch(SOURCES["attack_enterprise"]["url"])
    catalog = json.loads(index.body)
    collection = next(
        c for c in catalog["collections"] if c["name"].lower().startswith("enterprise")
    )
    newest = max(collection["versions"], key=lambda v: _version_key(v["version"]))
    bundle = fetch(newest["url"])
    objects = json.loads(bundle.body)["objects"]
    techniques: dict[str, dict[str, Any]] = {}
    for obj in objects:
        if obj.get("type") != "attack-pattern":
            continue
        external = next(
            (
                ref
                for ref in obj.get("external_references", [])
                if ref.get("source_name") == "mitre-attack" and ref.get("external_id")
            ),
            None,
        )
        if external is None:
            continue
        techniques[external["external_id"]] = {
            "name": obj.get("name", ""),
            "tactics": sorted(
                {
                    phase.get("phase_name", "")
                    for phase in obj.get("kill_chain_phases", [])
                    if phase.get("kill_chain_name") == "mitre-attack"
                }
            ),
            "sub_technique": bool(obj.get("x_mitre_is_subtechnique", False)),
            "deprecated": bool(obj.get("x_mitre_deprecated", False)),
            "revoked": bool(obj.get("revoked", False)),
        }
    payload = {
        "standard": "MITRE ATT&CK Enterprise",
        "version": newest["version"],
        "collection_modified": newest.get("modified", ""),
        "bundle_url": newest["url"],
        "technique_count": len(techniques),
        "techniques": dict(sorted(techniques.items())),
    }
    return Built(
        name="attack_enterprise",
        payload=payload,
        version=str(newest["version"]),
        version_source="collections[Enterprise ATT&CK].versions[max].version in index.json",
        sources=[index, bundle],
        license_note=SOURCES["attack_enterprise"]["license"],
        notes=[f"bundle {newest['url'].rsplit('/', 1)[-1]}"],
    )


def _version_key(raw: str) -> tuple[int, ...]:
    return tuple(int(part) if part.isdigit() else 0 for part in str(raw).split("."))


def build_d3fend() -> Built:
    fetched = fetch(SOURCES["d3fend"]["url"])
    graph = json.loads(fetched.body)["@graph"]
    version = ""
    release_date = ""
    license_value = ""
    for node in graph:
        types = node.get("@type")
        types = [types] if isinstance(types, str) else (types or [])
        if any("Ontology" in str(t) for t in types):
            version = _scalar(node.get("owl:versionInfo"))
            release_date = _scalar(node.get("d3f:release-date"))
            license_value = _scalar(node.get("dcterms:license"))
            break
    techniques: dict[str, dict[str, str]] = {}
    for node in graph:
        identifier = _scalar(node.get("d3f:d3fend-id"))
        if not identifier.startswith("D3-"):
            continue
        techniques[identifier] = {
            "label": _scalar(node.get("rdfs:label")),
            "id_iri": str(node.get("@id", "")),
        }
    payload = {
        "standard": "MITRE D3FEND",
        "version": version,
        "release_date": release_date,
        "declared_license": license_value,
        "technique_count": len(techniques),
        "techniques": dict(sorted(techniques.items())),
    }
    return Built(
        name="d3fend",
        payload=payload,
        version=version,
        version_source="owl:Ontology/owl:versionInfo in d3fend.json",
        sources=[fetched],
        license_note=f"ontology declares dcterms:license={license_value!r}",
        notes=[f"release date {release_date}"],
    )


def _scalar(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("@value", ""))
    if isinstance(value, list):
        for item in value:
            text = _scalar(item)
            if text:
                return text
        return ""
    return "" if value is None else str(value)


def build_owasp_api() -> Built:
    editions = fetch("https://api.github.com/repos/OWASP/API-Security/contents/editions")
    names = sorted(
        entry["name"] for entry in json.loads(editions.body) if entry.get("type") == "dir"
    )
    years = [name for name in names if name.isdigit()]
    current = max(years) if years else "2023"
    listing = fetch(SOURCES["owasp_api"]["url"])
    body = listing.body.decode("utf-8", errors="replace")
    categories: dict[str, str] = {}
    for match in re.finditer(rf"(API\d+:{current})\s*-\s*([^\]\n|]+)", body):
        title = match.group(2).strip().rstrip("].")
        categories.setdefault(match.group(1), title)
    payload = {
        "standard": "OWASP API Security Top 10",
        "version": current,
        "available_editions": years,
        "category_count": len(categories),
        "categories": dict(sorted(categories.items(), key=_owasp_sort)),
    }
    return Built(
        name="owasp_api",
        payload=payload,
        version=current,
        version_source="editions/ directory listing in the OWASP/API-Security repository",
        sources=[editions, listing],
        license_note=SOURCES["owasp_api"]["license"],
        notes=[f"editions present: {', '.join(years)}"],
    )


def _owasp_sort(item: tuple[str, Any]) -> tuple[int, str]:
    match = re.search(r"(\d+)", item[0])
    return (int(match.group(1)) if match else 10**9, item[0])


def build_owasp_llm() -> Built:
    fetched = fetch(SOURCES["owasp_llm"]["url"])
    raw = fetched.body.decode("utf-8", errors="replace")
    editions = sorted({m.group(1) for m in re.finditer(r"LLM\d{2}:(\d{4})", raw)})
    current = max(editions) if editions else ""
    risks: dict[str, str] = {}
    for match in re.finditer(rf">\s*(LLM\d{{2}}:{current})\s+([^<]{{3,80}}?)\s*<", raw):
        title = unescape(match.group(2)).strip()
        if title:
            risks.setdefault(match.group(1), title)
    payload = {
        "standard": "OWASP Top 10 for LLM Applications",
        "version": current,
        "available_editions": editions,
        "risk_count": len(risks),
        "risks": dict(sorted(risks.items(), key=_owasp_sort)),
    }
    return Built(
        name="owasp_llm",
        payload=payload,
        version=current,
        version_source="LLMnn:YYYY identifiers on the OWASP GenAI project page",
        sources=[fetched],
        license_note=SOURCES["owasp_llm"]["license"],
        notes=["titles taken from the anchor text of each risk on the project page"],
    )


METRIC_TABLE_ORDER = [
    ("AV", "Attack Vector / Modified Attack Vector", ["Network", "Adjacent", "Local", "Physical"]),
    ("AC", "Attack Complexity / Modified Attack Complexity", ["Low", "High"]),
    ("UI", "User Interaction / Modified User Interaction", ["None", "Required"]),
]


def build_cvss31() -> Built:
    fetched = fetch(SOURCES["cvss31"]["url"])
    text = re.sub(r"[ \t]+", " ", text_of(fetched))
    flat = re.sub(r"\s+", " ", text)
    notes: list[str] = []
    weights: dict[str, dict[str, float]] = {}

    for key, heading, labels in METRIC_TABLE_ORDER:
        section = _section_after(flat, heading, 200)
        values: dict[str, float] = {}
        for label in labels:
            match = re.search(rf"\b{label}\b\s+(\d+\.?\d*)", section)
            if match:
                values[label] = float(match.group(1))
        if len(values) == len(labels):
            weights[key] = values
        else:
            notes.append(f"UNVERIFIED: could not parse all {key} values from the specification")

    privileges = _section_after(flat, "Privileges Required / Modified Privileges Required", 240)
    pr_none = re.search(r"None\s+(\d+\.?\d*)", privileges)
    pr_low = re.search(r"Low\s+(\d+\.?\d*) \(or (\d+\.?\d*) if", privileges)
    pr_high = re.search(r"High\s+(\d+\.?\d*) \(or (\d+\.?\d*) if", privileges)
    if pr_none and pr_low and pr_high:
        weights["PR"] = {
            "None": float(pr_none.group(1)),
            "Low": float(pr_low.group(1)),
            "High": float(pr_high.group(1)),
        }
        weights["PR_scope_changed"] = {
            "None": float(pr_none.group(1)),
            "Low": float(pr_low.group(2)),
            "High": float(pr_high.group(2)),
        }
    else:
        notes.append("UNVERIFIED: could not parse Privileges Required values from the specification")

    cia = _section_after(flat, "Confidentiality / Integrity / Availability / Modified", 160)
    cia_values = {
        label: float(match.group(1))
        for label in ("High", "Low", "None")
        if (match := re.search(rf"\b{label}\b\s+(\d+\.?\d*)", cia))
    }
    if len(cia_values) == 3:
        weights["CIA"] = cia_values
    else:
        notes.append("UNVERIFIED: could not parse Confidentiality/Integrity/Availability values")

    bands: list[dict[str, Any]] = []
    scale = _section_after(flat, "Table 14: Qualitative severity rating scale", 320)
    for match in re.finditer(r"(None|Low|Medium|High|Critical)\s+(\d+\.\d+)(?:\s*-\s*(\d+\.\d+))?", scale):
        low = float(match.group(2))
        high = float(match.group(3)) if match.group(3) else low
        bands.append({"rating": match.group(1).lower(), "min": low, "max": high})
    if len(bands) != 5:
        notes.append("UNVERIFIED: could not parse the qualitative severity rating scale")
        bands = []

    equations = {
        "iss": _grab(flat, "ISS = 1 - [", 120),
        "impact_unchanged": _grab(flat, "Impact = If Scope is Unchanged", 120),
        "exploitability": _grab(flat, "Exploitability = 8.22", 140),
        "base_score": _grab(flat, "BaseScore = If Impact", 260),
        "roundup": _grab(flat, "Roundup returns the smallest number", 200),
        "roundup_appendix_a": _grab(flat, "function Roundup (input):", 240),
    }
    constants = {
        "impact_unchanged_factor": 6.42,
        "impact_changed_factor": 7.52,
        "impact_changed_subtrahend": 3.25,
        "impact_changed_iss_offset": 0.029,
        "impact_changed_power_offset": 0.02,
        "impact_changed_power": 15,
        "exploitability_factor": 8.22,
        "scope_changed_multiplier": 1.08,
    }
    for name, value in constants.items():
        if str(value) not in flat:
            notes.append(f"UNVERIFIED: constant {name}={value} not found verbatim in the specification")

    payload = {
        "standard": "CVSS",
        "version": "3.1",
        "weights": weights,
        "rating_bands": bands,
        "constants": constants,
        "equations_quoted": equations,
    }
    return Built(
        name="cvss31",
        payload=payload,
        version="3.1",
        version_source="FIRST CVSS v3.1 specification document, section 7.4 Table 16 and Table 14",
        sources=[fetched],
        license_note=SOURCES["cvss31"]["license"],
        notes=notes or ["all weights, bands and constants parsed from the specification"],
    )


def _section_after(text: str, marker: str, length: int) -> str:
    index = text.find(marker)
    return "" if index < 0 else text[index + len(marker) : index + len(marker) + length]


def _grab(text: str, marker: str, length: int) -> str:
    index = text.find(marker)
    return "" if index < 0 else re.sub(r"\s+", " ", text[index : index + length]).strip()


NVD_PAGES = [
    ("CRITICAL", 20),
    ("HIGH", 20),
    ("MEDIUM", 20),
    ("LOW", 20),
]

NVD_METRIC_FILTERS = [
    "PR:H",
    "AV:P",
    "AV:A",
    "PR:H/UI:N/S:C",
    "PR:L/UI:N/S:C",
    "AV:N/AC:L/PR:N/UI:R/S:C",
    "C:N/I:N/A:L",
]

NVD_RECORDS = [
    "CVE-2021-44228",
    "CVE-2019-0708",
    "CVE-2021-34527",
    "CVE-2022-22965",
    "CVE-2014-0160",
    "CVE-2017-5638",
    "CVE-2021-26855",
    "CVE-2020-1472",
    "CVE-2018-13379",
    "CVE-2022-0847",
    "CVE-2021-3156",
    "CVE-2019-11510",
    "CVE-2021-21972",
    "CVE-2019-19781",
    "CVE-2023-4863",
    "CVE-2022-26134",
    "CVE-2020-0601",
    "CVE-2021-40444",
]


def build_cvss31_vectors() -> Built:
    collected: dict[str, dict[str, Any]] = {}
    sources: list[Fetched] = []
    notes: list[str] = []
    queries = [
        f"{SOURCES['cvss31_vectors']['url']}?cvssV3Severity={severity}&resultsPerPage={count}&startIndex=0"
        for severity, count in NVD_PAGES
    ] + [
        f"{SOURCES['cvss31_vectors']['url']}?cvssV3Metrics={metric}&resultsPerPage=5&startIndex=0"
        for metric in NVD_METRIC_FILTERS
    ] + [f"{SOURCES['cvss31_vectors']['url']}?cveId={cve}" for cve in NVD_RECORDS]
    for url in queries:
        severity = url.rsplit("=", 1)[-1]
        try:
            fetched = fetch(url)
        except Exception as error:  # noqa: BLE001
            notes.append(f"UNVERIFIED: NVD page {severity} failed: {type(error).__name__}")
            continue
        sources.append(fetched)
        for item in json.loads(fetched.body).get("vulnerabilities", []):
            cve = item.get("cve", {})
            cve_id = cve.get("id", "")
            for metric in cve.get("metrics", {}).get("cvssMetricV31", []):
                data = metric.get("cvssData", {})
                vector = data.get("vectorString", "")
                score = data.get("baseScore")
                rating = str(data.get("baseSeverity", "")).lower()
                if not vector.startswith("CVSS:3.1/") or score is None:
                    continue
                if vector in collected and collected[vector]["type"] == "Primary":
                    continue
                collected[vector] = {
                    "base_score": float(score),
                    "rating": rating,
                    "cve": cve_id,
                    "source": metric.get("source", ""),
                    "type": metric.get("type", ""),
                }
        time.sleep(7)
    payload = {
        "standard": "CVSS v3.1 base score test vectors",
        "version": "3.1",
        "vector_count": len(collected),
        "origin": "NVD CVE API 2.0 cvssMetricV31 entries (NVD primary and CNA secondary), scored by the named source",
        "vectors": [
            {"vector": vector, **values} for vector, values in sorted(collected.items())
        ],
    }
    if len(collected) < 10:
        notes.append(f"UNVERIFIED: only {len(collected)} vectors collected, fewer than the 10 required")
    changed = sum(1 for vector in collected if "/S:C/" in vector)
    payload["scope_changed_count"] = changed
    if changed == 0:
        notes.append("UNVERIFIED: no Scope:Changed vector collected, so that branch is not tested against NVD")
    return Built(
        name="cvss31_vectors",
        payload=payload,
        version="3.1",
        version_source="NVD CVE API 2.0 cvssMetricV31 entries",
        sources=sources,
        license_note=SOURCES["cvss31_vectors"]["license"],
        notes=notes or [f"{len(collected)} official vector and score pairs"],
    )


def build_nist_sp_800_115() -> Built:
    fetched = fetch(SOURCES["nist_sp_800_115"]["url"])
    text = re.sub(r"\s+", " ", text_of(fetched))
    status = ""
    for candidate in ("Withdrawn", "Superseded", "Final"):
        if re.search(rf"\b{candidate}\b", text):
            status = candidate
            break
    title_match = re.search(r"SP 800-115,? ([A-Z][^|]{10,120}?)(?: \| CSRC|Date Published)", text)
    date_match = re.search(r"Date Published:? ([A-Za-z]+ \d{4})", text)
    notes: list[str] = [] if status else ["UNVERIFIED: could not read a publication status from the CSRC page"]
    pdf = fetch(SOURCES["nist_sp_800_115"]["pdf"])
    planning: list[dict[str, str]] = []
    roe_template: list[dict[str, str]] = []
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(pdf.body))
        document = "\n".join(page.extract_text() or "" for page in reader.pages)
        toc = document[document.find("6. Security Assessment Planning") :]
        for match in re.finditer(r"^(6\.\d)\s+([A-Z][A-Za-z ,&-]{3,60}?)\.{3,}", toc, re.M):
            planning.append({"section": match.group(1), "title": match.group(2).strip()})
            if match.group(1) == "6.7":
                break
        first = document.find("Rules of Engagement Template")
        start = document.find("Rules of Engagement Template", first + 30)
        end = document.find("Appendix C", start)
        body = document[start:end]
        for match in re.finditer(r"^\s*(\d+(?:\.\d+)*)\.\s+([A-Z][A-Za-z /,&()-]{2,60})\s*$", body, re.M):
            roe_template.append({"section": match.group(1), "title": match.group(2).strip()})
    except Exception as error:  # noqa: BLE001
        notes.append(f"UNVERIFIED: could not extract headings from the SP 800-115 PDF: {type(error).__name__}")
    if not planning:
        notes.append("UNVERIFIED: no section 6 planning headings extracted")
    if not roe_template:
        notes.append("UNVERIFIED: no Appendix B rules of engagement headings extracted")
    payload = {
        "standard": "NIST SP 800-115",
        "version": "original publication",
        "status_on_csrc": status,
        "title": (title_match.group(1).strip() if title_match else ""),
        "date_published": (date_match.group(1) if date_match else ""),
        "planning_sections": planning,
        "roe_template_sections": roe_template,
    }
    return Built(
        name="nist_sp_800_115",
        payload=payload,
        version=payload["date_published"] or "unknown",
        version_source="NIST CSRC publication detail page and the published PDF",
        sources=[fetched, pdf],
        license_note=SOURCES["nist_sp_800_115"]["license"],
        notes=notes or [f"CSRC status {status}"],
    )


BUILDERS = {
    "cwe": build_cwe,
    "attack_enterprise": build_attack_enterprise,
    "d3fend": build_d3fend,
    "owasp_api": build_owasp_api,
    "owasp_llm": build_owasp_llm,
    "cvss31": build_cvss31,
    "cvss31_vectors": build_cvss31_vectors,
    "nist_sp_800_115": build_nist_sp_800_115,
}


def write(built: Built) -> dict[str, Any]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / f"{built.name}.json"
    body = json.dumps(built.payload, indent=1, sort_keys=False, ensure_ascii=False) + "\n"
    path.write_text(body, encoding="utf-8")
    return {
        "name": built.name,
        "file": path.name,
        "file_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
        "version": built.version,
        "version_source": built.version_source,
        "retrieved_at": built.sources[0].retrieved_at if built.sources else "",
        "license_note": built.license_note,
        "landing_page": SOURCES.get(built.name, {}).get("landing", ""),
        "downloads": [
            {"url": source.url, "sha256": source.sha256, "bytes": len(source.body)}
            for source in built.sources
        ],
        "notes": built.notes,
        "unverified": [note for note in built.notes if note.startswith("UNVERIFIED")],
    }


def refresh(names: list[str]) -> dict[str, Any]:
    existing: dict[str, Any] = {}
    if PROVENANCE_FILE.is_file():
        existing = json.loads(PROVENANCE_FILE.read_text(encoding="utf-8"))
    entries: dict[str, Any] = dict(existing.get("sources", {}))
    for name in names:
        print(f"refreshing {name}", flush=True)
        entry = write(BUILDERS[name]())
        entries[name] = entry
        for note in entry["unverified"]:
            print(f"  {note}", flush=True)
    provenance = {
        "generated_by": "security_agents.standards.refresh",
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "note": "Identifiers and versions are taken from the primary sources listed here. Nothing in this directory is authored from memory.",
        "sources": dict(sorted(entries.items())),
    }
    PROVENANCE_FILE.write_text(
        json.dumps(provenance, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return provenance


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="security_agents.standards.refresh")
    parser.add_argument("--source", action="append", choices=sorted(BUILDERS), default=None)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args(argv)
    if args.list:
        for name, source in sorted(SOURCES.items()):
            print(f"{name}: {source['url']}")
        return 0
    names = sorted(BUILDERS) if args.all or not args.source else args.source
    provenance = refresh(names)
    unverified = [
        note
        for entry in provenance["sources"].values()
        for note in entry.get("unverified", [])
    ]
    print(f"wrote {len(names)} index files to {DATA_DIR}")
    if unverified:
        print("UNVERIFIED items:")
        for note in unverified:
            print(f"  {note}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
