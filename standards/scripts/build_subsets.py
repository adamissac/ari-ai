"""Rebuild the vendored framework subsets in ``standards/standards/data`` from official sources.

    uv run python standards/scripts/build_subsets.py --download /tmp/standards-src
    uv run python standards/scripts/build_subsets.py --src /tmp/standards-src

This is the only code path that touches the network, and it is never run by tests.
Each upstream file is checked against the SHA-256 pinned in ``SOURCES`` before anything
is extracted, so a silently changed upstream file fails the build instead of changing the
catalog. Extraction is deterministic (sorted keys, sorted entries), so re-running against
the same inputs reproduces the committed files byte for byte. To move to a new framework
release, update the URL/version/SHA-256 here, re-run, review the diff, and record the
change in ``docs/THIRD_PARTY_DATA.md``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any

DATA = Path(__file__).resolve().parents[1] / "standards" / "data"

FIRST_CALC_COMMIT = "c5b0d409ae9f57c44264c6ce5f27d89298e1d32a"
OWASP_COMMIT = "99f4395589bdbd120ae961f9cd179e79d7f9b27f"
OWASP_2026_COMMIT = "9253e38ade58e959b531c0c5c9a4842272c9cd0e"
OWASP_2026_FILES = {
    "LLM01_PromptInjection": "ff036047755c505e6d7837a0114f6056f8f751a3628061b6711b6eac19e1f8b0",
    "LLM02_SensitiveInformationDisclosure": "009153f4880fdabd79585cf1b74e60e2dfe79668c5581853890aa2bec36ab05e",
    "LLM03_ExcessiveAgency": "e961d0d9fe8382be4086aaddd65c1fad0d5d53220174493fe8c287f864c0529e",
    "LLM04_SupplyChain": "b5cb83fe937ecf38b8017918ac90b378da6d9c8ec9e2b485f422c08e4d66ac9e",
    "LLM05_DataModelPoisoning": "28ba5d86c102c82916066aae4bde2c10605cdb98cca51f572093ba002d2a198d",
    "LLM06_UnboundedConsumption": "e121147737d4750f89466fe191b5581fe71a822d8e1cfb621ea91d0d6a1dc6d5",
    "LLM07_Misinformation": "5686479c061cd2057b9905775ce70fc92b1b26e9daf296928521d56837ad4732",
    "LLM08_HiddenContextExposure": "e00d214f81757f626510df57e92116bec026b6c31ef7c3fb2bb52b71318c5ffe",
    "LLM09_VectorAndEmbeddingWeaknesses": "e1a3aff504a708d46c5dbf1c4bbc9ae05f3206cc6ea8e6e9d544b3f0d0ff7c23",
    "LLM10_ImproperOutputHandling": "d61a5ca0eddb38cdd0f485d642ed263c259638e2f1cf82eb1563c064491d67f0",
}
OWASP_FILES = [
    "LLM01_PromptInjection",
    "LLM02_SensitiveInformationDisclosure",
    "LLM03_SupplyChain",
    "LLM04_DataModelPoisoning",
    "LLM05_ImproperOutputHandling",
    "LLM06_ExcessiveAgency",
    "LLM07_SystemPromptLeakage",
    "LLM08_VectorAndEmbeddingWeaknesses",
    "LLM09_Misinformation",
    "LLM10_UnboundedConsumption",
]

SOURCES: dict[str, dict[str, str]] = {
    "enterprise-attack-20.0.json": {
        "url": "https://raw.githubusercontent.com/mitre-attack/attack-stix-data/master/enterprise-attack/enterprise-attack-20.0.json",
        "sha256": "81113ba98afa2928f3dcff62022539f7ce30c315c32e14422f11ff95ce534352",
    },
    "d3fend.json": {
        "url": "https://d3fend.mitre.org/ontologies/d3fend.json",
        "sha256": "e1546d432c6aa64d45b62dd9e9484b0774ae84de7ff3605ff9dd4e20278957bf",
    },
    "cwec_latest.xml.zip": {
        "url": "https://cwe.mitre.org/data/xml/cwec_latest.xml.zip",
        "sha256": "3976f599e5e5200219a3108bb896d06e2a88fbb293369e1883cb423a5e9d7d50",
    },
    "capec_latest.xml": {
        "url": "https://capec.mitre.org/data/xml/capec_latest.xml",
        "sha256": "70279a2dff0cb0ad79e546adb07828335a704ad5210e047e09e986172fc9e34d",
    },
    "NIST.SP.800-61r3.pdf": {
        "url": "https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-61r3.pdf",
        "sha256": "e5593d6bb85daecec7e8d9549400c7b3473bcc3f06e469c82218073afa7fba2d",
    },
    "first-examples.html": {
        "url": "https://www.first.org/cvss/v4.0/examples",
        "sha256": "e359060047b372609e7d782f82d594d13225b63f9d0c15b5b4358cf1b53b2f2a",
    },
    **{
        f"cvss/{name}": {
            "url": f"https://raw.githubusercontent.com/FIRSTdotorg/cvss-v4-calculator/{FIRST_CALC_COMMIT}/{name}",
            "sha256": sha,
        }
        for name, sha in {
            "cvss_lookup.js": "d533fe625d95e15b7b488a4bf93dab5f7df16b7e38b0c8ee01281d7b31a8165e",
            "max_composed.js": "be707cc82c17993a04a84e47b1a8aaa1d0d212b56852254659ce77fd7d959f63",
            "max_severity.js": "f838ecb41bfd5114456e7fa7df8a8449ca2735c176867886fa34bd011dee0b24",
            "metrics.js": "99ee2643587071bf744cd090c4bb2db58d523ed0276efd809871b00a12985a4c",
            "cvss_score.js": "453ce6767b5c3939b51d1f21315f2649e47b5abeca674be287e94b524472a1bc",
        }.items()
    },
    **{
        f"owasp/{name}.md": {
            "url": f"https://raw.githubusercontent.com/OWASP/www-project-top-10-for-large-language-model-applications/{OWASP_COMMIT}/2_0_vulns/{name}.md",
            "sha256": "",  # filled from the download; pinned in MANIFEST.json per file
        }
        for name in OWASP_FILES
    },
}
SOURCES.update(
    {
        f"owasp2026/{name}.md": {
            "url": f"https://raw.githubusercontent.com/GenAI-Security-Project/GenAI-LLM-Top10/{OWASP_2026_COMMIT}/2026/final/{name}.md",
            "sha256": digest,
        }
        for name, digest in OWASP_2026_FILES.items()
    }
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def download(dest: Path) -> None:
    for name, meta in SOURCES.items():
        target = dest / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(meta["url"], timeout=120) as resp:  # noqa: S310 - pinned https
            target.write_bytes(resp.read())
        print("downloaded", name)


def verify(src: Path) -> dict[str, str]:
    digests: dict[str, str] = {}
    for name, meta in SOURCES.items():
        digest = sha256_file(src / name)
        if meta["sha256"] and digest != meta["sha256"]:
            raise SystemExit(f"{name}: sha256 {digest} != pinned {meta['sha256']}")
        digests[name] = digest
    return digests


def write_json(name: str, value: Any) -> str:
    text = json.dumps(value, indent=1, sort_keys=True, ensure_ascii=False) + "\n"
    path = DATA / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return sha256_bytes(text.encode("utf-8"))


# ------------------------------------------------------------------ ATT&CK


def build_attack(src: Path) -> dict[str, Any]:
    bundle = json.loads((src / "enterprise-attack-20.0.json").read_text())
    objects = bundle["objects"]
    by_stix = {o["id"]: o for o in objects}

    def ext_id(obj: dict[str, Any]) -> str | None:
        for ref in obj.get("external_references", []):
            if ref.get("source_name") == "mitre-attack":
                return ref.get("external_id")
        return None

    def ext_url(obj: dict[str, Any]) -> str | None:
        for ref in obj.get("external_references", []):
            if ref.get("source_name") == "mitre-attack":
                return ref.get("url")
        return None

    revoked_by: dict[str, str] = {}
    for o in objects:
        if o.get("type") == "relationship" and o.get("relationship_type") == "revoked-by":
            target = by_stix.get(o["target_ref"])
            if target is not None and ext_id(target):
                revoked_by[o["source_ref"]] = ext_id(target)  # type: ignore[assignment]

    tactics = {}
    for o in objects:
        if o.get("type") == "x-mitre-tactic":
            tid = ext_id(o)
            if tid:
                tactics[tid] = {
                    "name": o["name"],
                    "shortname": o["x_mitre_shortname"],
                    "url": ext_url(o),
                    "deprecated": bool(o.get("x_mitre_deprecated") or o.get("revoked")),
                }
    techniques = {}
    for o in objects:
        if o.get("type") != "attack-pattern":
            continue
        tid = ext_id(o)
        if not tid:
            continue
        techniques[tid] = {
            "name": o["name"],
            "url": ext_url(o),
            "is_subtechnique": bool(o.get("x_mitre_is_subtechnique")),
            "tactics": sorted(
                p["phase_name"]
                for p in o.get("kill_chain_phases", [])
                if p.get("kill_chain_name") == "mitre-attack"
            ),
            "deprecated": bool(o.get("x_mitre_deprecated")),
            "revoked": bool(o.get("revoked")),
            "revoked_by": revoked_by.get(o["id"]),
            "object_version": o.get("x_mitre_version"),
        }
    return {
        "framework": "attack",
        "domain": "enterprise-attack",
        "version": "20.0",
        "tactics": dict(sorted(tactics.items())),
        "techniques": dict(sorted(techniques.items())),
    }


# ------------------------------------------------------------------ D3FEND


def build_d3fend(src: Path) -> dict[str, Any]:
    graph = json.loads((src / "d3fend.json").read_text())["@graph"]
    nodes = {n["@id"]: n for n in graph}
    version = next(n["owl:versionInfo"] for n in graph if "owl:versionInfo" in n)

    def parents(node: dict[str, Any]) -> list[str]:
        sub = node.get("rdfs:subClassOf", [])
        sub = sub if isinstance(sub, list) else [sub]
        return [
            s["@id"] for s in sub if isinstance(s, dict) and s.get("@id", "").startswith("d3f:")
        ]

    def tactic_of(node_id: str, seen: set[str] | None = None) -> str | None:
        seen = seen or set()
        if node_id in seen or node_id not in nodes:
            return None
        seen.add(node_id)
        node = nodes[node_id]
        enables = node.get("d3f:enables")
        if isinstance(enables, dict):
            label = nodes.get(enables["@id"], {}).get("rdfs:label")
            if label:
                return str(label)
        for parent in parents(node):
            found = tactic_of(parent, seen)
            if found:
                return found
        return None

    techniques = {}
    for n in graph:
        did = n.get("d3f:d3fend-id")
        if not did or not did.startswith("D3-"):
            continue
        local = n["@id"].split(":", 1)[1]
        parent_ids = [nodes[p].get("d3f:d3fend-id") for p in parents(n) if p in nodes]
        techniques[did] = {
            "name": n.get("rdfs:label", local),
            "url": f"https://d3fend.mitre.org/technique/d3f:{local}/",
            "tactic": tactic_of(n["@id"]),
            "parent": next((p for p in parent_ids if p and p.startswith("D3-")), None),
            "deprecated": bool(n.get("owl:deprecated")),
        }
    return {
        "framework": "d3fend",
        "version": version,
        "techniques": dict(sorted(techniques.items())),
    }


# ------------------------------------------------------------------ CWE / CAPEC

CWE_NS = {"c": "http://cwe.mitre.org/cwe-7"}
CAPEC_NS = {"c": "http://capec.mitre.org/capec-3"}


def build_cwe(src: Path) -> dict[str, Any]:
    with zipfile.ZipFile(src / "cwec_latest.xml.zip") as zf:
        name = next(n for n in zf.namelist() if n.endswith(".xml"))
        root = ET.fromstring(zf.read(name))
    entries: dict[str, Any] = {}
    for kind, tag in (("weakness", "Weakness"), ("category", "Category"), ("view", "View")):
        for el in root.iter(f"{{{CWE_NS['c']}}}{tag}"):
            usage = el.find("c:Mapping_Notes/c:Usage", CWE_NS)
            entry: dict[str, Any] = {
                "name": el.get("Name"),
                "kind": kind,
                "status": el.get("Status"),
                "mapping_usage": usage.text if usage is not None else None,
                "url": f"https://cwe.mitre.org/data/definitions/{el.get('ID')}.html",
            }
            if kind == "weakness":
                entry["abstraction"] = el.get("Abstraction")
                entry["capec"] = sorted(
                    {
                        f"CAPEC-{r.get('CAPEC_ID')}"
                        for r in el.findall(
                            "c:Related_Attack_Patterns/c:Related_Attack_Pattern", CWE_NS
                        )
                    },
                    key=lambda s: int(s.split("-")[1]),
                )
            entries[f"CWE-{el.get('ID')}"] = entry
    return {
        "framework": "cwe",
        "version": root.get("Version"),
        "date": root.get("Date"),
        "entries": dict(sorted(entries.items(), key=lambda kv: int(kv[0].split("-")[1]))),
    }


def build_capec(src: Path) -> dict[str, Any]:
    root = ET.parse(src / "capec_latest.xml").getroot()
    patterns = {}
    for el in root.iter(f"{{{CAPEC_NS['c']}}}Attack_Pattern"):
        attack = []
        for tm in el.findall("c:Taxonomy_Mappings/c:Taxonomy_Mapping", CAPEC_NS):
            if tm.get("Taxonomy_Name") == "ATTACK":
                entry = tm.find("c:Entry_ID", CAPEC_NS)
                if entry is not None and entry.text:
                    attack.append("T" + entry.text.strip())
        patterns[f"CAPEC-{el.get('ID')}"] = {
            "name": el.get("Name"),
            "status": el.get("Status"),
            "cwe": sorted(
                {
                    f"CWE-{r.get('CWE_ID')}"
                    for r in el.findall("c:Related_Weaknesses/c:Related_Weakness", CAPEC_NS)
                },
                key=lambda s: int(s.split("-")[1]),
            ),
            "attack": sorted(set(attack)),
            "url": f"https://capec.mitre.org/data/definitions/{el.get('ID')}.html",
        }
    return {
        "framework": "capec",
        "version": root.get("Version"),
        "date": root.get("Date"),
        "patterns": dict(sorted(patterns.items(), key=lambda kv: int(kv[0].split("-")[1]))),
    }


# ------------------------------------------------------------------ OWASP LLM


def build_owasp(src: Path, digests: dict[str, str]) -> dict[str, Any]:
    risks = {}
    for name in OWASP_FILES:
        text = (src / "owasp" / f"{name}.md").read_text(encoding="utf-8")
        m = re.match(r"^##\s+(LLM\d\d:2025)\s+(.+?)\s*$", text.splitlines()[0])
        if not m:
            raise SystemExit(f"unexpected OWASP heading in {name}")
        risks[m.group(1)] = {
            "name": m.group(2),
            "source_file": f"2_0_vulns/{name}.md",
            "source_sha256": digests[f"owasp/{name}.md"],
        }
    return {
        "framework": "owasp_llm",
        "version": "2025",
        "source_commit": OWASP_COMMIT,
        "url": "https://genai.owasp.org/resource/owasp-top-10-for-llm-applications-2025/",
        "risks": risks,
    }


def build_owasp2026(src: Path, digests: dict[str, str]) -> dict[str, Any]:
    risks = {}
    for name in OWASP_2026_FILES:
        source = f"owasp2026/{name}.md"
        text = (src / source).read_text(encoding="utf-8")
        match = re.fullmatch(r"##\s+(LLM\d\d:2026)\s+(.+?)\s*", text.splitlines()[0])
        if not match:
            raise SystemExit(f"unexpected OWASP 2026 heading in {name}")
        risks[match.group(1)] = {
            "name": match.group(2),
            "source_file": f"2026/final/{name}.md",
            "source_sha256": digests[source],
        }
    return {
        "framework": "owasp_llm",
        "version": "2026",
        "source_commit": OWASP_2026_COMMIT,
        "url": "https://github.com/GenAI-Security-Project/GenAI-LLM-Top10/tree/"
        + OWASP_2026_COMMIT
        + "/2026/final",
        "risks": risks,
    }


# ------------------------------------------------------------------ CVSS v4.0


def _js_object(path: Path, var: str) -> Any:
    """Parse the small JS object literals of the FIRST calculator into JSON."""
    text = path.read_text()
    body = text[text.index(var) :]
    body = body[body.index("=") + 1 :].strip()
    body = re.sub(r"//[^\n]*", "", body)
    body = re.sub(r"(?m)^\s*([A-Za-z0-9_]+)\s*:", r'"\1":', body)
    body = re.sub(r"([{,]\s*)(\d+)\s*:", r'\1"\2":', body)
    body = re.sub(r",(\s*[}\]])", r"\1", body)
    return json.loads(body)


def build_cvss(src: Path) -> dict[str, Any]:
    return {
        "version": "4.0",
        "source_commit": FIRST_CALC_COMMIT,
        "lookup": _js_object(src / "cvss/cvss_lookup.js", "cvssLookup_global"),
        "max_composed": _js_object(src / "cvss/max_composed.js", "maxComposed"),
        "max_severity": _js_object(src / "cvss/max_severity.js", "maxSeverity"),
        # A list, not an object: the specification order matters and JSON keys get sorted.
        "metrics": [
            [k, v] for k, v in _js_object(src / "cvss/metrics.js", "expectedMetricOrder").items()
        ],
    }


def build_cvss_examples(src: Path) -> dict[str, Any]:
    """Vector/score pairs exactly as printed on FIRST's v4.0 examples page.

    Only pairs where the page prints ``CVSS v4 Score: <label> <score>`` directly after the
    vector link are taken; anything else on the page (v3.1 comparisons) is ignored.
    """
    page = (src / "first-examples.html").read_text(encoding="utf-8")
    plain = re.sub(r"<[^>]+>", " ", page)
    plain = re.sub(r"\s+", " ", plain)
    vec = r"(CVSS:4\.0(?:/[A-Z]+:[A-Za-z]+)+)"
    detail: dict[str, float] = {}
    for m in re.finditer(vec + r"\s+CVSS v4 Score:\s*([A-Za-z+ ]+?)\s+(\d+(?:\.\d)?)\b", plain):
        detail.setdefault(m.group(1), float(m.group(3)))
    table: dict[str, float] = {}
    for m in re.finditer(
        r"v3\.1 v4\.0 [A-Za-z+ ]+? \d+(?:\.\d)? (\d+(?:\.\d)?) CVSS:3\.1/\S+ " + vec, plain
    ):
        table.setdefault(m.group(2), float(m.group(1)))
    examples = []
    for v in sorted(set(detail) | set(table)):
        entry: dict[str, Any] = {"vector": v}
        if v in table:
            entry["table_score"] = table[v]
        if v in detail:
            entry["detail_score"] = detail[v]
        examples.append(entry)
    return {
        "source": SOURCES["first-examples.html"]["url"],
        "source_sha256": SOURCES["first-examples.html"]["sha256"],
        "note": (
            "table_score is the v4.0 column of an example's v3.1/v4.0 comparison table; "
            "detail_score is the 'CVSS v4 Score' heading printed after a vector. The page "
            "is not always self-consistent; see cvss-v4.0-first-js-golden.json for the "
            "reference calculator's own output for every vector here."
        ),
        "examples": examples,
    }


def build_cvss_golden(src: Path, example_vectors: list[str]) -> dict[str, Any]:
    """Score vectors with FIRST's own JavaScript (requires `node`); seeded, deterministic."""
    import random
    import subprocess

    metrics = dict(_js_object(src / "cvss/metrics.js", "expectedMetricOrder"))
    base = ("AV", "AC", "AT", "PR", "UI", "VC", "VI", "VA", "SC", "SI", "SA")

    def render(sel: dict[str, str]) -> str:
        parts = ["CVSS:4.0"] + [f"{k}:{v}" for k, v in sel.items() if k in base or v != "X"]
        return "/".join(parts)

    rng = random.Random(20261017)
    vectors = list(example_vectors)
    vectors += [render({k: rng.choice(v) for k, v in metrics.items()}) for _ in range(1500)]
    vectors += [
        render({k: (rng.choice(v) if k in base else "X") for k, v in metrics.items()})
        for _ in range(1500)
    ]
    oracle = Path(__file__).with_name("first_js_oracle.js")
    proc = subprocess.run(
        ["node", str(oracle), str(src / "cvss")],
        input="\n".join(vectors),
        capture_output=True,
        text=True,
        check=True,
    )
    scored = [line.rsplit(" ", 1) for line in proc.stdout.strip().splitlines()]
    return {
        "generator": f"FIRST cvss-v4-calculator@{FIRST_CALC_COMMIT} cvss_score.js under node",
        "seed": 20261017,
        "vectors": [{"vector": v, "score": float(s)} for v, s in scored],
    }


# ------------------------------------------------------------------ main


def build(src: Path) -> None:
    digests = verify(src)
    produced = {
        "attack-enterprise.json": build_attack(src),
        "d3fend.json": build_d3fend(src),
        "cwe.json": build_cwe(src),
        "capec.json": build_capec(src),
        "owasp-llm.json": build_owasp(src, digests),
        "owasp-llm-2026.json": build_owasp2026(src, digests),
        "cvss-v4.0.json": build_cvss(src),
        "cvss-v4.0-first-examples.json": build_cvss_examples(src),
    }
    produced["cvss-v4.0-first-js-golden.json"] = build_cvss_golden(
        src, [e["vector"] for e in produced["cvss-v4.0-first-examples.json"]["examples"]]
    )
    upstream = {
        "attack-enterprise.json": ["enterprise-attack-20.0.json"],
        "d3fend.json": ["d3fend.json"],
        "cwe.json": ["cwec_latest.xml.zip"],
        "capec.json": ["capec_latest.xml"],
        "owasp-llm.json": [f"owasp/{n}.md" for n in OWASP_FILES],
        "owasp-llm-2026.json": [f"owasp2026/{n}.md" for n in OWASP_2026_FILES],
        "cvss-v4.0.json": [
            "cvss/cvss_lookup.js",
            "cvss/max_composed.js",
            "cvss/max_severity.js",
            "cvss/metrics.js",
            "cvss/cvss_score.js",
        ],
        "cvss-v4.0-first-examples.json": ["first-examples.html"],
        "cvss-v4.0-first-js-golden.json": [
            "cvss/cvss_lookup.js",
            "cvss/max_composed.js",
            "cvss/max_severity.js",
            "cvss/metrics.js",
            "cvss/cvss_score.js",
        ],
    }
    manifest_path = DATA / "MANIFEST.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {"files": {}}
    for name, value in produced.items():
        digest = write_json(name, value)
        entry = manifest["files"].setdefault(name, {})
        entry["sha256"] = digest
        entry["version"] = str(value.get("version", entry.get("version", "")))
        entry["upstream"] = [
            {"url": SOURCES[u]["url"], "sha256": digests[u]} for u in upstream[name]
        ]
    manifest_path.write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    print("wrote", ", ".join(produced))


CURATED: dict[str, dict[str, Any]] = {
    "nist-sp800-61r3.json": {
        "version": "Rev. 3 (CSF 2.0)",
        "upstream": ["NIST.SP.800-61r3.pdf"],
        "curated": "quoted from the pinned PDF; reviewed by hand",
    },
    "rules/check_attack.json": {"version": "1", "curated": "reviewed rule table"},
    "rules/fortify_d3fend.json": {"version": "1", "curated": "reviewed rule table"},
    "rules/rl_d3fend.json": {"version": "1", "curated": "reviewed rule table"},
    "rules/cvss_derivation.json": {"version": "1", "curated": "reviewed rule table"},
    "owasp-llm-coverage.json": {"version": "1", "curated": "platform self-assessment matrix"},
}


def refresh_curated() -> None:
    """Re-hash hand-curated files (rule tables, NIST subset, OWASP matrix) into the manifest."""
    manifest_path = DATA / "MANIFEST.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {"files": {}}
    for name, meta in CURATED.items():
        path = DATA / name
        if not path.exists():
            continue
        entry = manifest["files"].setdefault(name, {})
        entry["sha256"] = sha256_file(path)
        entry["version"] = meta["version"]
        entry["curated"] = meta["curated"]
        if "upstream" in meta:
            entry["upstream"] = [
                {"url": SOURCES[u]["url"], "sha256": SOURCES[u]["sha256"]} for u in meta["upstream"]
            ]
    manifest_path.write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    print("refreshed curated entries")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--src", type=Path)
    p.add_argument("--download", type=Path)
    p.add_argument(
        "--refresh-curated", action="store_true", help="only re-hash curated files (offline)"
    )
    args = p.parse_args(argv)
    if args.refresh_curated:
        refresh_curated()
        return 0
    if args.download:
        download(args.download)
        args.src = args.download
    if not args.src:
        p.error("--src or --download is required")
    build(args.src)
    return 0


if __name__ == "__main__":
    sys.exit(main())
