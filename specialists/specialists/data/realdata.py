"""Optional real-corpus rows, layered on top of the synthetic/MITRE datasets.

These loaders read downloaded public data from specialists/data/cache (never committed;
fetch it with python -m specialists.data.fetch). When the cache is absent every loader
returns nothing and the dataset builders fall back to the bundled data only, so training
stays reproducible on a clean checkout. Real rows are recorded in the dataset digest like
any other row, so a checkpoint manifest still pins exactly what it trained on.

Sources and licences:

* DiverseVul (Chen et al., RAID'23) — real functions labelled vulnerable/safe with CWE
  ids, each tied to a fixing commit. Used for Scout only: functions whose CWE is one of
  our 12 classes keep that label, other vulnerable functions become "vuln_other" (they
  ARE vulnerable but outside our class space — never labelled "safe"), and safe
  functions become "safe". C/C++ only; that mismatch is documented in the README.
* NVD CVE JSON 2.0 — CVE English descriptions with their CWE ids. Trace gets the
  description text as "name" input with the same CWE->CAPEC->ATT&CK tactic labels.
* MITRE ATT&CK STIX bundle — technique descriptions. Fortify gets extra "name" rows
  whose text is the technique description (same labels), so the model sees technique
  wording beyond short titles.

Splitting is honest: DiverseVul rows split by commit id (all functions of a commit stay
together), NVD rows split by CWE id (same bucket as the CWE row), ATT&CK description
rows keep the technique's split.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import zlib
from pathlib import Path
from typing import Any

CACHE = Path(os.environ.get("SPECIALISTS_DATA_CACHE", Path(__file__).parent / "cache"))

# Scout's class space (12 CWEs + safe). Everything else vulnerable is "vuln_other".
VULN_OTHER = "vuln_other"

OUR_SCOUT_CWES = [
    "CWE-22", "CWE-78", "CWE-79", "CWE-89", "CWE-502", "CWE-639", "CWE-798",
    "CWE-862", "CWE-916", "CWE-918", "CWE-942", "CWE-1284",
]


def _cwe_of(value: str) -> str | None:
    m = re.match(r"CWE-(\d+)", value.strip(), re.I)
    return f"CWE-{int(m.group(1))}" if m else None


def diversevul(cache: Path = CACHE, *, max_per_label: int = 30000) -> list[dict[str, Any]]:
    """Real functions -> {code, label, family}. Split buckets by commit id; 0 test, 1 val."""
    files = sorted(cache.glob("dv-train-*.parquet"))
    if not files:
        return []
    import pyarrow.parquet as pq  # train-time extra; never imported at inference

    ours = set(OUR_SCOUT_CWES)
    rows: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    for f in files:
        d = pq.read_table(f, columns=["func", "target", "cwe", "commit_id", "project"]).to_pydict()
        for func, target, cwes, commit, _project in zip(
            d["func"], d["target"], d["cwe"], d["commit_id"], d["project"], strict=True
        ):
            if not isinstance(func, str) or len(func) < 40:
                continue
            if target == 1:
                hit = next((c for c in (cwes or []) if c in ours), None)
                label = hit or VULN_OTHER
            else:
                label = "safe"
            if counts.get(label, 0) >= max_per_label:
                continue
            counts[label] = counts.get(label, 0) + 1
            bucket = zlib.crc32(str(commit).encode()) % 6
            split = {0: "test", 1: "val"}.get(bucket, "train")
            rows.append({
                "family": f"dv:{commit}", "split": split, "framework": "c",
                "code": func[:20000], "label": label,
            })
    return rows


def nvd_cves(cache: Path = CACHE) -> list[dict[str, Any]]:
    """CVE descriptions with CWE ids -> {id, desc, cwe[]}."""
    path = cache / "nvd-cves.jsonl"
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text().splitlines():
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        cwes = sorted({_c for c in r.get("cwe", []) if (_c := _cwe_of(c))})
        if r.get("desc") and cwes:
            rows.append({"id": r["id"], "desc": r["desc"], "cwe": cwes})
    return rows


def attack_descriptions(cache: Path = CACHE) -> dict[str, str]:
    """ATT&CK technique id -> description text, from the Enterprise STIX bundle."""
    path = cache / "enterprise-attack-stix.json"
    if not path.is_file():
        return {}
    out: dict[str, str] = {}
    for o in json.loads(path.read_text())["objects"]:
        if o.get("type") != "attack-pattern" or o.get("revoked") or o.get("x_mitre_deprecated"):
            continue
        ext = next(
            (e.get("external_id") for e in o.get("external_references", [])
             if e.get("source_name") == "mitre-attack"),
            None,
        )
        if ext and o.get("description"):
            out[ext] = re.sub(r"\s+", " ", o["description"]).strip()
    return out


def data_digest() -> str:
    """SHA-256 over whatever real rows are actually present (recorded in manifests)."""
    h = hashlib.sha256()
    h.update(json.dumps([(r["id"], r["cwe"]) for r in nvd_cves()], sort_keys=True).encode())
    for p in sorted(CACHE.glob("dv-train-*.parquet")) + [CACHE / "enterprise-attack-stix.json"]:
        if p.is_file():
            h.update(p.name.encode())
            h.update(hashlib.sha256(p.read_bytes()).digest())
    return h.hexdigest()
