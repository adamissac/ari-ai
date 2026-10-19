"""Download the optional real corpora used by the dataset builders.

    uv run --extra train python -m specialists.data.fetch

Writes into specialists/data/cache (git-ignored; delete freely and re-run):
  dv-train-*.parquet        DiverseVul train split (HF mirror of the RAID'23 release)
  nvd-cves.jsonl            NVD CVEs (JSON 2.0) reduced to {id, desc, cwe[]}
  enterprise-attack-stix.json  MITRE ATT&CK Enterprise STIX bundle

Public data only. No customer code, no third-party private repos.
"""

from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

CACHE = Path(__file__).parent / "cache"

DV_FILES = [
    "train-00000-of-00002-06b0cca04c9bb0f2.parquet",
    "train-00001-of-00002-0fb7d9c1c879fb27.parquet",
]
DV_BASE = "https://huggingface.co/datasets/bstee615/diversevul/resolve/main/data/"
ATTACK_URL = "https://raw.githubusercontent.com/mitre-attack/attack-stix-data/master/enterprise-attack/enterprise-attack.json"
NVD = "https://services.nvd.nist.gov/rest/json/cves/2.0"
NVD_PAGES = 8  # ~16k CVEs from index 0; pass --pages to go deeper
NVD_RANGES = [("2019-01-01T00:00:00.000", "2020-01-01T00:00:00.000"),
              ("2021-01-01T00:00:00.000", "2022-01-01T00:00:00.000")]


def _get(url: str, dest: Path | None = None) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "ari-specialists/1.0"})
    with urllib.request.urlopen(req, timeout=300) as r:
        blob = r.read()
    if dest:
        dest.write_bytes(blob)
    return blob


def main() -> int:

    CACHE.mkdir(exist_ok=True)
    for name in DV_FILES:
        dest = CACHE / f"dv-{name}"
        if not dest.is_file():
            print("downloading", name, flush=True)
            _get(DV_BASE + name, dest)
        print(dest.name, dest.stat().st_size)
    stix = CACHE / "enterprise-attack-stix.json"
    if not stix.is_file():
        print("downloading ATT&CK STIX", flush=True)
        _get(ATTACK_URL, stix)
    nvd = (CACHE / "nvd-cves.jsonl").open("a")
    seen = {json.loads(line)["id"] for line in (CACHE / "nvd-cves.jsonl").open() if line.strip()} \
        if (CACHE / "nvd-cves.jsonl").is_file() else set()
    windows = [None] + NVD_RANGES
    for win in windows:
        for start in range(0, NVD_PAGES * 2000, 2000):
            q = f"?resultsPerPage=2000&startIndex={start}"
            if win:
                q += f"&pubStartDate={win[0]}&pubEndDate={win[1]}"
            data = None
            for attempt in range(4):
                try:
                    data = json.loads(_get(NVD + q))
                    break
                except Exception as exc:  # noqa: BLE001 - retry then give up
                    print(start, "retry", attempt, exc)
                    time.sleep(15)
            if data is None:
                break
            for v in data["vulnerabilities"]:
                c = v["cve"]
                if c["id"] in seen:
                    continue
                desc = next((x["value"] for x in c["descriptions"] if x["lang"] == "en"), "")
                cwes = [x["description"][0]["value"] for x in c.get("weaknesses", []) if x.get("description")]
                cwes = [w for w in cwes if w.startswith("CWE-") and w not in ("NVD-CWE-noinfo", "NVD-CWE-Other")]
                if desc and cwes:
                    print(json.dumps({"id": c["id"], "desc": desc, "cwe": cwes}), file=nvd)
                    seen.add(c["id"])
            nvd.flush()
            print("nvd", win or "all", start, "total", len(data["vulnerabilities"]), flush=True)
            time.sleep(6)
    nvd.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
