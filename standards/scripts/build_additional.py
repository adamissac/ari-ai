from __future__ import annotations

import argparse
import io
import json
import re
import sys
import urllib.request
from html import unescape
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from build_subsets import DATA, sha256_bytes, sha256_file, write_json  # noqa: E402

OWASP_API_COMMIT = "ea77cba533150900a7d0c3822d75c460f52edef1"

ADDITIONAL_SOURCES: dict[str, dict[str, str]] = {
    "cvss-v3.1-specification.html": {
        "url": "https://www.first.org/cvss/v3.1/specification-document",
        "sha256": "",
    },
    "owasp-api-2023/0x11-t10.md": {
        "url": f"https://raw.githubusercontent.com/OWASP/API-Security/{OWASP_API_COMMIT}/editions/2023/en/0x11-t10.md",
        "sha256": "",
    },
    "nist-sp800-115.pdf": {
        "url": "https://nvlpubs.nist.gov/nistpubs/Legacy/SP/nistspecialpublication800-115.pdf",
        "sha256": "",
    },
    "nist-sp800-115-csrc.html": {
        "url": "https://csrc.nist.gov/pubs/sp/800/115/final",
        "sha256": "",
    },
    "sarif-schema-2.1.0.json": {
        "url": "https://docs.oasis-open.org/sarif/sarif/v2.1.0/errata01/os/schemas/sarif-schema-2.1.0.json",
        "sha256": "",
    },
    "sarif-v2.1.0-errata01-os-complete.html": {
        "url": "https://docs.oasis-open.org/sarif/sarif/v2.1.0/errata01/os/sarif-v2.1.0-errata01-os-complete.html",
        "sha256": "",
    },
}

PINS_FILE = HERE / "additional_pins.json"

LICENSES = {
    "cvss-v3.1.json": "FIRST CVSS terms: owned by FIRST and used by permission; publish the vector with every score",
    "owasp-api-2023.json": "CC BY-SA 4.0 (OWASP API Security Project); identifiers and verbatim titles only",
    "nist-sp800-115.json": "NIST public information (https://www.nist.gov/copyrights-disclaimers); credit requested",
    "cvss-v3.1-nvd-vectors.json": "UNVERIFIED: NVD terms page returned a Cloudflare challenge; CVE ids, vectors and scores only",
    "rules/cwe_owasp_api.json": "project mapping authored in this repository",
    "sarif-2.1.0.json": "OASIS copyright and IPR notice copied from the pinned specification into the file's notice field; schema stored for validation only",
}


def pins() -> dict[str, str]:
    return json.loads(PINS_FILE.read_text()) if PINS_FILE.exists() else {}


def download(dest: Path, names: list[str] | None = None) -> None:
    for name, meta in ADDITIONAL_SOURCES.items():
        if names and name not in names:
            continue
        target = dest / name
        target.parent.mkdir(parents=True, exist_ok=True)
        request = urllib.request.Request(
            meta["url"], headers={"User-Agent": "hackatl standards build"}
        )
        with urllib.request.urlopen(request, timeout=180) as response:  # noqa: S310
            target.write_bytes(response.read())
        print("downloaded", name)


def verify(src: Path, *, repin: bool, names: list[str] | None = None) -> dict[str, str]:
    pinned = pins()
    digests: dict[str, str] = {}
    for name in names or list(ADDITIONAL_SOURCES):
        digest = sha256_file(src / name)
        expected = pinned.get(name)
        if expected and digest != expected and not repin:
            raise SystemExit(
                f"{name}: sha256 {digest} != pinned {expected}; rerun with --repin to accept"
            )
        digests[name] = digest
    if repin or not pinned or any(name not in pinned for name in digests):
        PINS_FILE.write_text(json.dumps({**pinned, **digests}, indent=1, sort_keys=True) + "\n")
    return digests


def _text(raw: bytes, encoding: str = "utf-8") -> str:
    text = raw.decode(encoding, errors="replace")
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", text, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", unescape(text))


def _after(text: str, marker: str, length: int) -> str:
    index = text.find(marker)
    return "" if index < 0 else text[index + len(marker) : index + len(marker) + length]


def build_cvss31(src: Path) -> dict[str, Any]:
    flat = _text((src / "cvss-v3.1-specification.html").read_bytes())
    weights: dict[str, dict[str, float]] = {}
    for key, heading, labels in (
        (
            "AV",
            "Attack Vector / Modified Attack Vector",
            ["Network", "Adjacent", "Local", "Physical"],
        ),
        ("AC", "Attack Complexity / Modified Attack Complexity", ["Low", "High"]),
        ("UI", "User Interaction / Modified User Interaction", ["None", "Required"]),
    ):
        section = _after(flat, heading, 200)
        values = {
            label: float(m.group(1))
            for label in labels
            if (m := re.search(rf"\b{label}\b\s+(\d+\.?\d*)", section))
        }
        if len(values) != len(labels):
            raise SystemExit(f"could not parse {key} weights from the CVSS v3.1 specification")
        weights[key] = values
    privileges = _after(flat, "Privileges Required / Modified Privileges Required", 240)
    none = re.search(r"None\s+(\d+\.?\d*)", privileges)
    low = re.search(r"Low\s+(\d+\.?\d*) \(or (\d+\.?\d*) if", privileges)
    high = re.search(r"High\s+(\d+\.?\d*) \(or (\d+\.?\d*) if", privileges)
    if not (none and low and high):
        raise SystemExit("could not parse Privileges Required weights")
    weights["PR"] = {
        "None": float(none.group(1)),
        "Low": float(low.group(1)),
        "High": float(high.group(1)),
    }
    weights["PR_scope_changed"] = {
        "None": float(none.group(1)),
        "Low": float(low.group(2)),
        "High": float(high.group(2)),
    }
    cia = _after(flat, "Confidentiality / Integrity / Availability / Modified", 160)
    weights["CIA"] = {
        label: float(m.group(1))
        for label in ("High", "Low", "None")
        if (m := re.search(rf"\b{label}\b\s+(\d+\.?\d*)", cia))
    }
    if len(weights["CIA"]) != 3:
        raise SystemExit("could not parse Confidentiality/Integrity/Availability weights")
    scale = _after(flat, "Table 14: Qualitative severity rating scale", 320)
    bands = [
        {
            "rating": m.group(1).lower(),
            "min": float(m.group(2)),
            "max": float(m.group(3)) if m.group(3) else float(m.group(2)),
        }
        for m in re.finditer(
            r"(None|Low|Medium|High|Critical)\s+(\d+\.\d+)(?:\s*-\s*(\d+\.\d+))?", scale
        )
    ]
    if len(bands) != 5:
        raise SystemExit("could not parse the qualitative severity rating scale")
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
    missing = [name for name, value in constants.items() if str(value) not in flat]
    if missing:
        raise SystemExit(f"constants not found verbatim in the specification: {missing}")

    def quote(marker: str, length: int) -> str:
        index = flat.find(marker)
        return "" if index < 0 else flat[index : index + length].strip()

    return {
        "framework": "cvss",
        "version": "3.1",
        "weights": weights,
        "rating_bands": bands,
        "constants": constants,
        "equations_quoted": {
            "iss": quote("ISS = 1 - [", 120),
            "impact_unchanged": quote("Impact = If Scope is Unchanged", 120),
            "exploitability": quote("Exploitability = 8.22", 140),
            "base_score": quote("BaseScore = If Impact", 260),
            "roundup": quote("Roundup returns the smallest number", 200),
            "roundup_appendix_a": quote("function Roundup (input):", 240),
        },
        "terms_quoted": quote("While FIRST owns all right and interest", 600),
    }


def build_owasp_api(src: Path) -> dict[str, Any]:
    body = (src / "owasp-api-2023/0x11-t10.md").read_text(encoding="utf-8")
    categories: dict[str, dict[str, str]] = {}
    for match in re.finditer(r"(API\d+:2023)\s*-\s*([^\]\n|]+)", body):
        title = match.group(2).strip().rstrip("].")
        categories.setdefault(match.group(1), {"name": title})
    if len(categories) != 10:
        raise SystemExit(f"expected 10 OWASP API 2023 categories, parsed {len(categories)}")
    return {
        "framework": "owasp_api",
        "version": "2023",
        "editions_observed": ["2019", "2023"],
        "source_commit": OWASP_API_COMMIT,
        "categories": dict(
            sorted(categories.items(), key=lambda item: int(item[0][3:].split(":")[0]))
        ),
    }


def build_sp800115(src: Path) -> dict[str, Any]:
    try:
        from pypdf import PdfReader
    except ImportError as error:
        raise SystemExit(
            "pypdf is required to rebuild nist-sp800-115.json (pip install pypdf)"
        ) from error
    reader = PdfReader(io.BytesIO((src / "nist-sp800-115.pdf").read_bytes()))
    document = "\n".join(page.extract_text() or "" for page in reader.pages)
    toc = document[document.find("6. Security Assessment Planning") :]
    planning = []
    for match in re.finditer(r"^(6\.\d)\s+([A-Z][A-Za-z ,&-]{3,60}?)\.{3,}", toc, re.M):
        planning.append({"section": match.group(1), "title": match.group(2).strip()})
        if match.group(1) == "6.7":
            break
    first = document.find("Rules of Engagement Template")
    start = document.find("Rules of Engagement Template", first + 30)
    body = document[start : document.find("Appendix C", start)]
    template = [
        {"section": m.group(1), "title": m.group(2).strip()}
        for m in re.finditer(
            r"^\s*(\d+(?:\.\d+)*)\.\s+([A-Z][A-Za-z /,&()-]{2,60})\s*$", body, re.M
        )
    ]
    page = _text((src / "nist-sp800-115-csrc.html").read_bytes())
    status = next(
        (s for s in ("Withdrawn", "Superseded", "Final") if re.search(rf"\b{s}\b", page)), ""
    )
    date = re.search(r"Date Published:? ([A-Za-z]+ \d{4})", page)
    if len(planning) != 7 or len(template) != 21 or not status:
        raise SystemExit("could not extract SP 800-115 status and headings")
    return {
        "framework": "nist_sp800_115",
        "version": date.group(1) if date else "September 2008",
        "title": "Technical Guide to Information Security Testing and Assessment",
        "status_on_csrc": status,
        "planning_sections": planning,
        "roe_template_sections": template,
    }


def build_sarif(src: Path) -> dict[str, Any]:
    schema = json.loads((src / "sarif-schema-2.1.0.json").read_bytes())
    page = _text((src / "sarif-v2.1.0-errata01-os-complete.html").read_bytes(), "windows-1252")
    stage = re.search(
        r"OASIS Standard incorporating Approved Errata\s+(\d{1,2} [A-Z][a-z]+ \d{4})", page
    )
    start = page.find("Copyright")
    end = page.find("Table of Contents", start)
    if not stage or start < 0 or end < 0 or "version 2.1.0" not in schema.get("title", "").lower():
        raise SystemExit("could not extract the SARIF stage, notice or schema title")
    return {
        "framework": "sarif",
        "version": "2.1.0",
        "stage": "OASIS Standard incorporating Approved Errata",
        "date": stage.group(1),
        "notice": page[start:end].strip(),
        "schema": schema,
    }


BUILDERS = {
    "cvss-v3.1.json": (build_cvss31, ["cvss-v3.1-specification.html"]),
    "owasp-api-2023.json": (build_owasp_api, ["owasp-api-2023/0x11-t10.md"]),
    "nist-sp800-115.json": (build_sp800115, ["nist-sp800-115.pdf", "nist-sp800-115-csrc.html"]),
    "sarif-2.1.0.json": (
        build_sarif,
        ["sarif-schema-2.1.0.json", "sarif-v2.1.0-errata01-os-complete.html"],
    ),
}

CURATED = {
    "cvss-v3.1-nvd-vectors.json": "vector and score pairs retrieved from the NVD CVE API; NVD data is mutable, so the recorded response hashes are provenance, not a reproducible pin",
    "rules/cwe_owasp_api.json": "project mapping: CWE to OWASP API Security Top 10 2023, CWEs limited to MITRE usage Allowed or Allowed-with-Review",
}


def build(src: Path, *, repin: bool, only: list[str] | None = None) -> None:
    selected = {name: BUILDERS[name] for name in (only or list(BUILDERS))}
    digests = verify(
        src, repin=repin, names=sorted({u for _, ins in selected.values() for u in ins})
    )
    manifest_path = DATA / "MANIFEST.json"
    manifest = json.loads(manifest_path.read_text())
    for name, (builder, inputs) in selected.items():
        value = builder(src)
        entry = manifest["files"].setdefault(name, {})
        entry["sha256"] = write_json(name, value)
        entry["version"] = str(value.get("version", ""))
        entry["license"] = LICENSES[name]
        entry["upstream"] = [
            {"url": ADDITIONAL_SOURCES[u]["url"], "sha256": digests[u]} for u in inputs
        ]
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print("wrote", ", ".join(selected))
    refresh_curated()


def refresh_curated() -> None:
    manifest_path = DATA / "MANIFEST.json"
    manifest = json.loads(manifest_path.read_text())
    for name, note in CURATED.items():
        path = DATA / name
        if not path.exists():
            continue
        entry = manifest["files"].setdefault(name, {})
        entry["sha256"] = sha256_file(path)
        entry["curated"] = note
        entry["license"] = LICENSES[name]
        data = json.loads(path.read_text())
        entry["version"] = str(data.get("version", "1"))
        if "upstream" in data:
            entry["upstream"] = data["upstream"]
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print("refreshed curated entries:", ", ".join(CURATED))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="build_additional")
    parser.add_argument("--src", type=Path)
    parser.add_argument("--download", type=Path)
    parser.add_argument("--repin", action="store_true")
    parser.add_argument("--refresh-curated", action="store_true")
    parser.add_argument("--only", action="append", choices=sorted(BUILDERS))
    args = parser.parse_args(argv)
    if args.refresh_curated:
        refresh_curated()
        return 0
    if args.download:
        wanted = sorted({u for n in (args.only or BUILDERS) for u in BUILDERS[n][1]})
        download(args.download, wanted)
        args.src = args.download
    if not args.src:
        parser.error("--src or --download is required")
    build(args.src, repin=args.repin, only=args.only)
    return 0


if __name__ == "__main__":
    sys.exit(main())


__all__ = ["ADDITIONAL_SOURCES", "build", "sha256_bytes"]
