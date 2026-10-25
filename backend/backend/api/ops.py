"""Operator endpoints: storage reporting and on-demand maintenance.

Entirely disabled unless OPS_API_TOKEN is set — a Bearer token checked in constant
time, independent of user sessions/CSRF (this surface is for automation and on-call,
not the UI). See docs/deploy/POSTGRES_STORAGE.md.
"""

from __future__ import annotations

import hmac
import logging
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend import maintenance
from backend.db import get_engine
from backend.settings import get_settings

router = APIRouter()
log = logging.getLogger("backend.api.ops")


def _require_ops(request: Request, authorization: str | None = Header(default=None)) -> None:
    token = get_settings().ops_api_token
    destructive_request = request.method == "POST" and request.url.path.endswith("/ops/maintenance")
    if token is None:
        if destructive_request:
            log.warning("destructive maintenance request refused: ops API is disabled")
        # Disabled ops surface must look like it does not exist.
        raise HTTPException(status_code=404, detail="not found")
    secret = token.get_secret_value()
    scheme, _, presented = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not hmac.compare_digest(presented, secret):
        if destructive_request:
            log.warning("destructive maintenance request refused: invalid ops authorization")
        raise HTTPException(status_code=401, detail="unauthorized")


@router.get("/ops/storage", dependencies=[Depends(_require_ops)])
def storage_report() -> Any:
    """Current database/WAL/table/filesystem usage plus reclaimable estimates."""
    return maintenance.storage_report(engine=get_engine())


class MaintenanceRequest(BaseModel):
    dry_run: bool = True
    confirm_plan_digest: str | None = None


@router.post("/ops/maintenance", dependencies=[Depends(_require_ops)])
def run_maintenance(
    body: MaintenanceRequest,
    destructive_token: str | None = Header(default=None, alias="X-Ops-Destructive-Token"),
) -> Any:
    """Run a dry-run report or a separately authorized destructive cycle."""
    engine = get_engine()
    settings = get_settings()
    if body.dry_run:
        return maintenance.run_retention(engine=engine, dry_run=True)
    if settings.retention_dry_run:
        log.warning("destructive maintenance request refused: retention dry-run is enforced")
        return JSONResponse(status_code=409, content={"detail": "retention dry-run is enforced"})
    expected = settings.ops_destructive_token
    if expected is None:
        log.warning("destructive maintenance request refused: destructive maintenance disabled")
        return JSONResponse(status_code=403, content={"detail": "destructive maintenance disabled"})
    if destructive_token is None or not hmac.compare_digest(
        destructive_token, expected.get_secret_value()
    ):
        log.warning("destructive maintenance request refused: invalid destructive token")
        return JSONResponse(status_code=403, content={"detail": "invalid destructive token"})
    plan = maintenance.run_retention(engine=engine, s=settings, dry_run=True)
    if body.confirm_plan_digest is None or not hmac.compare_digest(
        body.confirm_plan_digest, plan["plan_digest"]
    ):
        log.warning("destructive maintenance request refused: plan digest mismatch")
        return JSONResponse(
            status_code=409,
            content={
                "detail": {
                    "message": "maintenance plan digest mismatch",
                    "plan_digest": plan["plan_digest"],
                }
            },
        )
    log.warning("destructive maintenance request accepted plan_digest=%s", plan["plan_digest"])
    return maintenance.run_retention(
        engine=engine,
        s=settings,
        dry_run=False,
        confirmed_snapshot_ids=set(plan["snapshot_ids"]),
    )


@router.get("/ops/storage/prometheus", dependencies=[Depends(_require_ops)])
def storage_prometheus() -> Any:
    """Same numbers in Prometheus text exposition format for external scrapers."""
    report = maintenance.storage_report(engine=get_engine())
    lines = [
        "# HELP ari_postgres_bytes PostgreSQL database size in bytes",
        "# TYPE ari_postgres_bytes gauge",
        f"ari_postgres_bytes {report['database']['size_bytes']}",
        "# HELP ari_postgres_wal_bytes WAL directory size in bytes",
        "# TYPE ari_postgres_wal_bytes gauge",
        f"ari_postgres_wal_bytes {report['wal_bytes'] or 0}",
        "# HELP ari_postgres_table_bytes Total relation size by table",
        "# TYPE ari_postgres_table_bytes gauge",
    ]
    for t in report["tables"]:
        lines.append(f'ari_postgres_table_bytes{{table="{t["table"]}"}} {t["total_bytes"]}')
    pct = report["volume"]["pct_used"]
    if pct is not None:
        lines += [
            "# HELP ari_postgres_volume_pct Volume utilization percent",
            "# TYPE ari_postgres_volume_pct gauge",
            f"ari_postgres_volume_pct {pct}",
        ]
    data_volume = report["data_volume"]
    data_used = data_volume["used_bytes"]
    if data_used is not None:
        lines += [
            "# HELP ari_data_volume_bytes App data volume usage in bytes",
            "# TYPE ari_data_volume_bytes gauge",
            f"ari_data_volume_bytes {data_used}",
        ]
    data_pct = data_volume["pct_used"]
    if data_pct is not None:
        lines += [
            "# HELP ari_data_volume_pct App data volume utilization percent",
            "# TYPE ari_data_volume_pct gauge",
            f"ari_data_volume_pct {data_pct}",
        ]
    fs = report.get("filesystem", {})
    if "artifact_bytes" in fs:
        lines.append(f"ari_artifact_store_bytes {fs['artifact_bytes']}")
    if "workdir_bytes" in fs:
        lines.append(f"ari_security_workdir_bytes {fs['workdir_bytes']}")
    from fastapi import Response

    return Response("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")


@router.post("/ops/maintenance/dry-run-report", dependencies=[Depends(_require_ops)])
def dry_run_report() -> Any:
    """What the next real cycle would delete, without deleting it."""
    return maintenance.run_retention(engine=get_engine(), dry_run=True)
