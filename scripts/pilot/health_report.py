"""Per-customer pilot health report (docs/pilot/METRICS.md) over the product API.

Reads only membership-gated endpoints with one owner session, so a report can only ever
contain the organization that session belongs to. Every number is counted from persisted
records; nothing is estimated. Output stays outside the product (coordination/status/ or
the ops spreadsheet).

    ARI_SESSION=<hackatl_session cookie> uv run python scripts/pilot/health_report.py \
        --base-url https://<backend> --project prj_... [--json]

The session value is read from the environment and never printed.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from collections import Counter
from collections.abc import Callable, Iterable
from datetime import UTC, datetime, timedelta
from typing import Any

Get = Callable[[str, dict[str, Any] | None], dict[str, Any]]

CONFIRMED = {
    "validated",
    "diagnosed",
    "patch_proposed",
    "verified",
    "patch_rejected",
    "unresolved",
    "hardened",
}
VERIFIED = {"verified", "hardened"}
FIX_WRITTEN = {"patch_proposed", "verified", "patch_rejected", "hardened"}
STOPPED = {"FAILED", "CANCELLED", "BUDGET_EXHAUSTED"}
STALE_APPROVAL = timedelta(hours=48)


def _ts(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


def _pages(get: Get, path: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    cursor: str | None = None
    while True:
        body = get(path, {"limit": 200, **({"cursor": cursor} if cursor else {})})
        items.extend(body["items"])
        cursor = body.get("next_cursor")
        if not cursor:
            return items


def collect(get: Get, project_id: str) -> dict[str, Any]:
    """Fetch everything the report needs for one project. Any non-2xx raises (the caller's
    `get` decides), so a partial report is never produced."""
    asms = _pages(get, f"/api/v1/projects/{project_id}/assessments")
    return {
        "project": get(f"/api/v1/projects/{project_id}", None),
        "repositories": get(f"/api/v1/projects/{project_id}/repositories", None)["items"],
        "assessments": asms,
        "runs": {a["id"]: get(f"/api/v1/assessments/{a['id']}/runs", None)["items"] for a in asms},
        "findings": get(f"/api/v1/projects/{project_id}/findings", None)["items"],
        "approvals": get(f"/api/v1/projects/{project_id}/approvals", None)["items"],
    }


def _reached(finding: dict[str, Any]) -> dict[str, datetime | None]:
    """Each status the finding has held, with when it first got there. History survives a
    later disposition (accepted risk, closed), so it is the record of what the run proved."""
    first: dict[str, datetime | None] = {}
    for h in finding.get("history") or []:
        first.setdefault(h["to_status"], _ts(h.get("at")))
        if h.get("from_status"):
            first.setdefault(h["from_status"], None)
    first.setdefault(finding["status"], None)
    return first


def _first(times: Iterable[datetime | None]) -> datetime | None:
    known = [t for t in times if t is not None]
    return min(known) if known else None


def _minutes(start: datetime | None, end: datetime | None) -> float | None:
    return round((end - start).total_seconds() / 60, 1) if start and end else None


def summarize(data: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    asms, findings, approvals = data["assessments"], data["findings"], data["approvals"]
    states = Counter(a["state"] for a in asms)
    completed = [a for a in asms if a["state"] == "COMPLETED"]
    durations = sorted(
        (end - start).total_seconds()
        for a in completed
        if (start := _ts(a["created_at"])) and (end := _ts(a.get("completed_at")))
    )
    live = [
        aid for aid, rs in data["runs"].items() if any(r.get("provider_mode") == "live" for r in rs)
    ]
    reached = {f["id"]: _reached(f) for f in findings}

    def held(f: dict[str, Any], statuses: set[str]) -> bool:
        return bool(statuses & reached[f["id"]].keys())

    def when(statuses: set[str]) -> datetime | None:
        return _first(t for r in reached.values() for s, t in r.items() if s in statuses)

    created = _ts(data["project"].get("created_at"))
    pending = [a for a in approvals if a["status"] == "pending"]
    usd = round(sum(a.get("usage", {}).get("usd", 0.0) for a in asms), 4)
    return {
        "project": {"id": data["project"]["id"], "name": data["project"]["name"]},
        "repositories": len(data["repositories"]),
        "assessments": {
            "total": len(asms),
            "by_state": dict(sorted(states.items())),
            "completed": len(completed),
            "stopped": sum(states[s] for s in STOPPED),
            "with_live_model_runs": len(live),
            "duration_s_p50": round(statistics.median(durations), 1) if durations else None,
            "duration_s_max": round(durations[-1], 1) if durations else None,
            "usd_total": usd,
            "usd_per_completed": round(usd / len(completed), 4) if completed else None,
        },
        "findings": {
            "total": len(findings),
            "security_confirmed": sum(
                1 for f in findings if f["kind"] == "security" and held(f, CONFIRMED)
            ),
            "functional_confirmed": sum(
                1 for f in findings if f["kind"] == "functional" and held(f, CONFIRMED)
            ),
            "ruled_out": sum(
                1 for f in findings if held(f, {"refuted"}) and not held(f, CONFIRMED)
            ),
            "unconfirmed": sum(1 for f in findings if not held(f, CONFIRMED | {"refuted"})),
            "fix_written": sum(1 for f in findings if held(f, FIX_WRITTEN)),
            "fix_verified": sum(1 for f in findings if held(f, VERIFIED)),
            "accepted_risk": sum(1 for f in findings if f["status"] == "accepted_risk"),
        },
        "approvals": {
            "pending": len(pending),
            "stale_pending": sum(
                1 for a in pending if (t := _ts(a.get("requested_at"))) and now - t > STALE_APPROVAL
            ),
            "approved": sum(1 for a in approvals if a["status"] == "approved"),
            "declined": sum(1 for a in approvals if a["status"] == "declined"),
        },
        # Minutes from project creation. None means the milestone has not happened (or its
        # time was not recorded), never zero.
        "activation_minutes": {
            "first_assessment": _minutes(created, _first(_ts(a["created_at"]) for a in asms)),
            "first_completed": _minutes(
                created, _first(_ts(a.get("completed_at")) for a in completed)
            ),
            "first_confirmed_finding": _minutes(created, when(CONFIRMED)),
            "first_verified_fix": _minutes(created, when(VERIFIED)),
        },
        "model_runs": dict(
            sorted(
                Counter(
                    r.get("provider_mode", "unknown") for rs in data["runs"].values() for r in rs
                ).items()
            )
        ),
    }


def render(report: dict[str, Any]) -> str:
    a, f, ap, t = (
        report[k] for k in ("assessments", "findings", "approvals", "activation_minutes")
    )

    def m(v: float | None) -> str:
        return "not yet" if v is None else f"{v} min"

    lines = [
        f"# Pilot health: {report['project']['name']} ({report['project']['id']})",
        "",
        f"- Repositories connected: {report['repositories']}",
        f"- Assessments: {a['total']} ({a['completed']} completed, {a['stopped']} stopped, "
        f"{a['with_live_model_runs']} with live model runs). States: {a['by_state']}",
        f"- Duration of completed assessments, p50 / max: {a['duration_s_p50']} s / {a['duration_s_max']} s",
        f"- Model spend: ${a['usd_total']} total, ${a['usd_per_completed']} per completed assessment",
        f"- Findings: {f['total']} ({f['security_confirmed']} security and {f['functional_confirmed']} "
        f"functional confirmed by an executed check, {f['ruled_out']} ruled out, "
        f"{f['unconfirmed']} unconfirmed)",
        f"- Fixes: {f['fix_written']} written, {f['fix_verified']} accepted by an independent re-test; "
        f"{f['accepted_risk']} findings accepted as risk",
        f"- Approvals: {ap['pending']} pending ({ap['stale_pending']} older than 48 h), "
        f"{ap['approved']} approved, {ap['declined']} declined",
        f"- Time from project creation: first assessment {m(t['first_assessment'])}, first completed "
        f"{m(t['first_completed'])}, first confirmed finding {m(t['first_confirmed_finding'])}, "
        f"first verified fix {m(t['first_verified_fix'])}",
        f"- Model runs by provider mode: {report['model_runs']}",
    ]
    if a["total"] and not a["with_live_model_runs"]:
        lines.append("")
        lines.append("No assessment had a live model run: these are not live-provider results.")
    return "\n".join(lines) + "\n"


def http_get(base_url: str, session: str) -> Get:
    import httpx

    client = httpx.Client(base_url=base_url, cookies={"hackatl_session": session}, timeout=30)

    def get(path: str, params: dict[str, Any] | None) -> dict[str, Any]:
        r = client.get(path, params=params)
        r.raise_for_status()
        return r.json()  # type: ignore[no-any-return]

    return get


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Per-customer pilot health report.")
    p.add_argument("--base-url", required=True)
    p.add_argument("--project", required=True)
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    session = os.environ.get("ARI_SESSION")
    if not session:
        print("ARI_SESSION is not set (an owner's hackatl_session cookie).", file=sys.stderr)
        return 2
    report = summarize(collect(http_get(args.base_url, session), args.project))
    sys.stdout.write(json.dumps(report, indent=2) + "\n" if args.json else render(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
