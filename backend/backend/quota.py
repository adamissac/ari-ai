"""Shared rolling-window review quotas for project assessment starts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.db import assessments
from backend.settings import get_settings

QuotaReason = Literal["hour", "day", "spend"]


@dataclass(frozen=True)
class QuotaDecision:
    reason: QuotaReason
    resets_at: datetime
    limit: int | None = None


def check_project_quota(conn: Connection, project_id: str, now: datetime) -> QuotaDecision | None:
    """Check every project's assessment start and the global rolling spend ceilings."""
    # This is check-then-insert, so concurrent starts can overshoot the limit.
    settings = get_settings()
    hour_window = timedelta(hours=1)
    day_window = timedelta(days=1)
    hour_filters = (
        assessments.c.project_id == project_id,
        assessments.c.created_at > now - hour_window,
        assessments.c.created_at <= now,
    )

    hour_count, hour_oldest = conn.execute(
        sa.select(sa.func.count(), sa.func.min(assessments.c.created_at)).where(*hour_filters)
    ).one()
    if hour_count >= settings.project_assessments_per_hour and hour_oldest is not None:
        hour_reset_at = conn.execute(
            sa.select(assessments.c.created_at)
            .where(*hour_filters)
            .order_by(assessments.c.created_at.asc())
            .offset(hour_count - settings.project_assessments_per_hour)
            .limit(1)
        ).scalar_one_or_none()
        return QuotaDecision(
            "hour",
            (hour_reset_at or hour_oldest) + hour_window,
            settings.project_assessments_per_hour,
        )

    day_filters = (
        assessments.c.project_id == project_id,
        assessments.c.created_at > now - day_window,
        assessments.c.created_at <= now,
    )
    day_count, day_oldest = conn.execute(
        sa.select(sa.func.count(), sa.func.min(assessments.c.created_at)).where(*day_filters)
    ).one()
    if day_count >= settings.project_assessments_per_day and day_oldest is not None:
        day_reset_at = conn.execute(
            sa.select(assessments.c.created_at)
            .where(*day_filters)
            .order_by(assessments.c.created_at.asc())
            .offset(day_count - settings.project_assessments_per_day)
            .limit(1)
        ).scalar_one_or_none()
        return QuotaDecision(
            "day",
            (day_reset_at or day_oldest) + day_window,
            settings.project_assessments_per_day,
        )

    usage_usd = sa.func.coalesce(
        sa.func.sum(assessments.c.doc["usage"]["usd"].astext.cast(sa.Numeric)), 0
    )
    positive_usage = sa.func.coalesce(assessments.c.doc["usage"]["usd"].astext.cast(sa.Numeric), 0)
    spent, spend_oldest = conn.execute(
        sa.select(usage_usd, sa.func.min(assessments.c.created_at)).where(
            assessments.c.created_at > now - day_window,
            assessments.c.created_at <= now,
            positive_usage > 0,
        )
    ).one()
    if float(spent) >= settings.assessments_usd_per_day and spend_oldest is not None:
        remaining = float(spent)
        spend_rows = conn.execute(
            sa.select(assessments.c.created_at, positive_usage.label("usage_usd"))
            .where(
                assessments.c.created_at > now - day_window,
                assessments.c.created_at <= now,
                positive_usage > 0,
            )
            .order_by(assessments.c.created_at.asc())
        )
        for created_at, usage_usd_value in spend_rows:
            remaining -= float(usage_usd_value)
            if remaining < settings.assessments_usd_per_day:
                return QuotaDecision("spend", created_at + day_window)
        return QuotaDecision("spend", spend_oldest + day_window)

    return None


def skipped_reason(decision: QuotaDecision) -> str:
    if decision.reason == "hour":
        return f"skipped: project review limit reached ({decision.limit}/hour)"
    if decision.reason == "day":
        return f"skipped: project review limit reached ({decision.limit}/day)"
    return "skipped: daily spend cap reached"


def rate_limit_message(decision: QuotaDecision) -> str:
    if decision.reason == "hour":
        message = f"project review limit reached ({decision.limit} per hour)"
    elif decision.reason == "day":
        message = f"project review limit reached ({decision.limit} per day)"
    else:
        message = "daily spend cap reached"
    return f"{message}; resets at {decision.resets_at.isoformat()}"
