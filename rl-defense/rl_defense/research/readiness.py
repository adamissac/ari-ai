"""Read-only audit of retained finite-case evidence; never authorizes training."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import NoReturn

from shared.evidence import EvidenceRef

ROOT = Path(__file__).resolve().parents[3]
BUNDLE = "rl-defense/results/deterministic-feasibility-001"
PROTOCOL = "docs/research/deterministic-feasibility/PROTOCOL.json"
INDEX_SHA = "fcc6298c432134269fc5f87d111be8347f149e1d0cced81c0352c096a57a8b6e"
POLICIES = ("unguarded", "blanket_deny", "exact_resource_guard")


def _digest(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def _read(path: Path, limit: int = 2 * 1024 * 1024) -> bytes:
    with path.open("rb") as stream:
        blob = stream.read(limit + 1)
    if len(blob) > limit:
        raise ValueError("readiness artifact exceeds size limit")
    return blob


def _json(blob: bytes) -> dict:
    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate evidence JSON key")
            result[key] = value
        return result

    def nonfinite(value: str) -> NoReturn:
        raise ValueError(f"nonfinite JSON value: {value}")

    value = json.loads(blob, object_pairs_hook=unique, parse_constant=nonfinite)
    if not isinstance(value, dict):
        raise ValueError("evidence must be a JSON object")
    return value


def _validate(protocol: dict, result: dict) -> dict:
    if (
        protocol.get("schema") != "deterministic-read-feasibility/1"
        or result.get("schema") != "deterministic-read-feasibility-evidence/1"
        or protocol["policies"] != list(POLICIES)
        or protocol["max_requests"] != 54
        or len(protocol["cases"]) != 18
        or result.get("finite_fixture_only") is not True
        or result.get("model_training") is not False
        or result.get("production_safety_established") is not False
    ):
        raise ValueError("unsupported finite-fixture evidence profile")
    cases = {case["name"]: case for case in protocol["cases"]}
    if len(cases) != 18:
        raise ValueError("duplicate protocol cases")
    rows = result["requests"]
    if len(rows) != 54:
        raise ValueError("incomplete request units")
    expected = [(case["name"], policy) for case in protocol["cases"] for policy in POLICIES]
    if [(row["case"], row["policy"]) for row in rows] != expected:
        raise ValueError("request units differ from the registered order")
    for row in rows:
        if (
            set(row) != {"case", "policy", "label", "status", "forwarded"}
            or row["label"] != cases[row["case"]]["label"]
            or row["label"] not in ("unauthorized", "owner", "delegate", "unknown")
            or type(row["status"]) is not int
            or row["status"] not in (200, 404, 503)
            or type(row["forwarded"]) is not bool
            or row["forwarded"] != (row["status"] == 200)
        ):
            raise ValueError("inconsistent finite-fixture request record")
    summaries = {}
    for policy in POLICIES:
        selected = [row for row in rows if row["policy"] == policy]
        failures = [
            row["case"]
            for row in selected
            if (row["label"] == "unauthorized" and row["status"] == 200)
            or (row["label"] in ("owner", "delegate") and row["status"] != 200)
        ]
        unknown = [row for row in selected if row["label"] == "unknown"]
        summaries[policy] = dict(
            successful_unauthorized_reads=sum(
                row["label"] == "unauthorized" and row["status"] == 200 for row in selected
            ),
            owner_denials=sum(row["label"] == "owner" and row["status"] != 200 for row in selected),
            delegated_denials=sum(
                row["label"] == "delegate" and row["status"] != 200 for row in selected
            ),
            known_case_failures=failures,
            passes_owner_limits=not failures,
            unknown_cases=unknown,
            unknowns_all_not_forwarded=all(not row["forwarded"] for row in unknown),
        )
    # JSON equality distinguishes booleans from numeric lookalikes.
    if json.dumps(result["summary"], sort_keys=True) != json.dumps(summaries, sort_keys=True):
        raise ValueError("reported summary differs from the retained request records")
    return summaries


def audit(bundle: Path) -> dict:
    """Trust the fixed original index, not hashes chosen by a copied bundle."""
    index_blob = _read(bundle / "EVIDENCE.json", 65536)
    if _digest(index_blob) != INDEX_SHA:
        raise ValueError("original evidence index trust anchor mismatch")
    index = _json(index_blob)
    result_blob = _read(bundle / "RESULT.json")
    if _digest(result_blob) != index["result_sha256"]:
        raise ValueError("retained result hash mismatch")
    result = _json(result_blob)
    source = index["source_commit"]
    if (
        len(source) != 40
        or any(c not in "0123456789abcdef" for c in source)
        or result["source_commit"] != source
        or result["protocol_sha256"] != index["protocol_sha256"]
    ):
        raise ValueError("execution source/protocol identity mismatch")
    raw_commit = subprocess.check_output(["git", "cat-file", "commit", source], cwd=ROOT)
    if (
        hashlib.sha1(b"commit " + str(len(raw_commit)).encode() + b"\0" + raw_commit).hexdigest()
        != source
    ):
        raise ValueError("source commit object mismatch")
    protocol_blob = subprocess.check_output(["git", "show", f"{source}:{PROTOCOL}"], cwd=ROOT)
    if _digest(protocol_blob) != index["protocol_sha256"]:
        raise ValueError("protocol does not belong to execution source")
    summaries = _validate(_json(protocol_blob), result)
    ref = EvidenceRef(
        kind="artifact",
        path=f"{BUNDLE}/RESULT.json",
        artifact_id=f"art_{index['result_sha256'][:26]}",
        sha256=index["result_sha256"],
        provenance="rl_defense.research.readiness@1",
        note="Original finite authored HTTP fixture; not production evidence",
    )
    return dict(
        schema="finite-fixture-readiness-audit/1",
        artifact_integrity_verified=True,
        auditor_commit=subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        auditor_python=sys.version,
        execution_commit=source,
        execution_tree=raw_commit.splitlines()[0].decode().removeprefix("tree "),
        protocol_sha256=index["protocol_sha256"],
        evidence=[ref.model_dump(mode="json", exclude_none=True)],
        request_units=54,
        numeric_summaries=summaries,
        timing_budget_verified=None,
        original_python_runtime_verified=None,
        canonical_payment_authority_verified=None,
        database_consistency_verified=None,
        population_feasibility_verified=None,
        readiness="inconclusive",
        rl_training_ready=False,
        promotion_ready=False,
        reasons=[
            "Original run did not record complete elapsed-time evidence or final deadline check",
            "Original interpreter identity was not recorded; dependency versions alone are insufficient",
            "Authored fixture cases do not establish population feasibility",
            "Canonical payment authority and transactional integration are unverified",
        ],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, default=ROOT / BUNDLE)
    args = parser.parse_args()
    from rl_defense.research.snapshot import source_snapshot, verification_commit

    bundle = args.bundle.resolve()
    commit = verification_commit(ROOT)
    with source_snapshot(ROOT, commit) as checkout:
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join(
            str(checkout / p) for p in ("rl-defense", "shared", "standards")
        )
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["GIT_OPTIONAL_LOCKS"] = "0"
        command = "import json,sys; from pathlib import Path; from rl_defense.research.readiness import audit; print(json.dumps(audit(Path(sys.argv[1])), sort_keys=True, indent=2))"
        result = subprocess.run(
            [sys.executable, "-c", command, str(bundle)],
            cwd=checkout,
            env=env,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        print(result.stdout, end="")


if __name__ == "__main__":
    main()
