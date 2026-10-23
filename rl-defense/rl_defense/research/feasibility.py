"""Explicit finite-case HTTP comparison; never imported by serving or training."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path

from fastapi import FastAPI
from starlette.responses import JSONResponse
from starlette.testclient import TestClient

from rl_defense.research.authorization import ReadContext, ReadGrant, authorize_read
from rl_defense.research.proof import environment_packages

ROOT = Path(__file__).resolve().parents[3]
PROTOCOL = "docs/research/deterministic-feasibility/PROTOCOL.json"


def execute_request(context: ReadContext, *, now: int, policy: str) -> tuple[int, bool]:
    """Independent HTTP fixture with no traffic-generator inputs or real network."""
    if policy not in ("unguarded", "blanket_deny", "exact_resource_guard"):
        raise ValueError("unsupported fixed policy")
    app = FastAPI()
    forwarded = []

    @app.middleware("http")
    async def guard(request, call_next):
        if policy == "blanket_deny":
            return JSONResponse({}, status_code=404)
        if policy == "exact_resource_guard":
            decision = authorize_read(context, now=now)
            if decision.outcome != "allow":
                return JSONResponse({}, status_code=404 if decision.outcome == "deny" else 503)
        return await call_next(request)

    @app.get("/payments/payment-1")
    def read():
        forwarded.append(True)
        return {"resource": "payment-1", "owner": "owner"}

    with TestClient(app) as client:
        response = client.get("/payments/payment-1")
    return response.status_code, bool(forwarded)


def run(output: Path, *, expected_protocol_sha256: str) -> dict:
    """Require a committed preregistration and a fresh output path; no retries."""
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT).strip():
        raise ValueError("comparison requires a clean committed checkout")
    source = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    blob = subprocess.check_output(["git", "show", f"{source}:{PROTOCOL}"], cwd=ROOT)
    if hashlib.sha256(blob).hexdigest() != expected_protocol_sha256:
        raise ValueError("preregistered protocol hash mismatch")
    protocol = json.loads(blob)
    if (
        protocol["schema"] != "deterministic-read-feasibility/1"
        or protocol["policies"] != ["unguarded", "blanket_deny", "exact_resource_guard"]
        or any(
            c["label"] not in ("unauthorized", "owner", "delegate", "unknown")
            for c in protocol["cases"]
        )
        or protocol["owner_approved_limits"]["successful_unauthorized_reads"] != 0
        or protocol["owner_approved_limits"]["legitimate_denials"] != 0
    ):
        raise ValueError("unsupported feasibility protocol")
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    rows = []
    try:
        for case in protocol["cases"]:
            data = dict(case["context"])
            if data["grants"] is not None:
                data["grants"] = tuple(ReadGrant(**g) for g in data["grants"])
            context = ReadContext(**data)
            for policy in protocol["policies"]:
                if time.monotonic() - started > protocol["compute_limit_seconds"]:
                    raise TimeoutError("preregistered compute limit exceeded")
                status, forwarded = execute_request(context, now=case["now"], policy=policy)
                rows.append(
                    dict(
                        case=case["name"],
                        label=case["label"],
                        policy=policy,
                        status=status,
                        forwarded=forwarded,
                    )
                )
                if len(rows) > protocol["max_requests"]:
                    raise ValueError("request budget exceeded")
        if len(rows) != protocol["max_requests"]:
            raise ValueError("incomplete preregistered comparison")
        summary = {}
        for policy in protocol["policies"]:
            selected = [r for r in rows if r["policy"] == policy]
            failures = [
                r["case"]
                for r in selected
                if (
                    r["label"] == "unauthorized"
                    and r["status"] == 200
                    or r["label"] in ("owner", "delegate")
                    and r["status"] != 200
                )
            ]
            unknown = [r for r in selected if r["label"] == "unknown"]
            summary[policy] = dict(
                successful_unauthorized_reads=sum(
                    r["label"] == "unauthorized" and r["status"] == 200 for r in selected
                ),
                owner_denials=sum(r["label"] == "owner" and r["status"] != 200 for r in selected),
                delegated_denials=sum(
                    r["label"] == "delegate" and r["status"] != 200 for r in selected
                ),
                known_case_failures=failures,
                passes_owner_limits=not failures,
                unknown_cases=unknown,
                unknowns_all_not_forwarded=all(not r["forwarded"] for r in unknown),
            )
        result = dict(
            schema="deterministic-read-feasibility-evidence/1",
            source_commit=source,
            protocol_sha256=expected_protocol_sha256,
            environment_packages=environment_packages(),
            requests=rows,
            summary=summary,
            finite_fixture_only=True,
            model_training=False,
            production_safety_established=False,
        )
        evidence = output / "RESULT.json"
        evidence.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
        (output / "EVIDENCE.json").write_text(
            json.dumps(
                dict(
                    source_commit=source,
                    protocol_sha256=expected_protocol_sha256,
                    result_sha256=hashlib.sha256(evidence.read_bytes()).hexdigest(),
                ),
                sort_keys=True,
                indent=2,
            )
            + "\n"
        )
        return result
    except Exception as exc:
        (output / "FAILURE.json").write_text(
            json.dumps(
                dict(
                    source_commit=source,
                    error_type=type(exc).__name__,
                    error=str(exc),
                    completed_requests=rows,
                    automatic_retry=False,
                ),
                sort_keys=True,
                indent=2,
            )
            + "\n"
        )
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--protocol-sha256", required=True)
    args = parser.parse_args()
    result = run(args.output, expected_protocol_sha256=args.protocol_sha256)
    print(json.dumps(result["summary"], sort_keys=True))


if __name__ == "__main__":
    main()
