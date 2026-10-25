"""Shared rolling-window quota for project assessment starts."""

from __future__ import annotations

from datetime import datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.db import assessments
from backend.settings import get_settings


def project_quota_delay_s(conn: Connection, project_id: str, now: datetime) -> float:
    settings = get_settings()
    delay_s = 0.0
    for window_s, limit in (
        (3600, settings.project_assessments_per_hour),
        (86400, settings.project_assessments_per_day),
    ):
        count, oldest = conn.execute(
            sa.select(sa.func.count(), sa.func.min(assessments.c.created_at)).where(
                assessments.c.project_id == project_id,
                assessments.c.created_at > now - timedelta(seconds=window_s),
                assessments.c.created_at <= now,
            )
        ).one()
        if count >= limit and oldest is not None:
            delay_s = max(
                delay_s,
                (oldest + timedelta(seconds=window_s + 1) - now).total_seconds(),
            )
    return delay_s
