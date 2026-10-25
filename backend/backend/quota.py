"""Shared rolling-window review quotas for project assessment starts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.db import assessments
from backend.services import project_settings
from backend.settings import get_settings
from shared.assessment import AssessmentTrigger

QuotaReason = Literal["hour", "day", "spend"]


@dataclass(frozen=True)
class QuotaDecision:
    reason: QuotaReason
    resets_at: datetime
    limit: int | None = None


def _quota_resets_at(
    conn: Connection,
    project_id: str,
    now: datetime,
    window: timedelta,
    count: int,
    limit: int,
    *,
    manual: bool = False,
) -> datetime:
    filters = [
        assessments.c.project_id == project_id,
        assessments.c.created_at > now - window,
        assessments.c.created_at <= now,
    ]
    if manual:
        filters.append(assessments.c.trigger == AssessmentTrigger.manual.value)
    next_expiring = conn.execute(
        sa.select(assessments.c.created_at)
        .where(*filters)
        .order_by(assessments.c.created_at.asc())
        .offset(count - limit)
        .limit(1)
    ).scalar_one()
    return next_expiring + window


def check_project_quota(
    conn: Connection, project_id: str, now: datetime, *, manual: bool = False
) -> QuotaDecision | None:
    """Apply all-trigger automatic or manual-only project quotas and the shared spend cap."""
    # This is check-then-insert, so concurrent starts can overshoot the limit.
    settings = get_settings()
    hour_window = timedelta(hours=1)
    day_window = timedelta(days=1)

    hour_filters = [
        assessments.c.project_id == project_id,
        assessments.c.created_at > now - hour_window,
        assessments.c.created_at <= now,
    ]
    if manual:
        hour_filters.append(assessments.c.trigger == AssessmentTrigger.manual.value)
    hour_count, hour_oldest = conn.execute(
        sa.select(sa.func.count(), sa.func.min(assessments.c.created_at)).where(*hour_filters)
    ).one()
    project_hour_cap = project_settings(conn, project_id).review.max_reviews_per_hour
    hour_limit = (
        min(settings.project_assessments_per_hour, project_hour_cap)
        if project_hour_cap is not None
        else settings.project_assessments_per_hour
    )
    if hour_count >= hour_limit and hour_oldest is not None:
        return QuotaDecision(
            "hour",
            _quota_resets_at(
                conn,
                project_id,
                now,
                hour_window,
                hour_count,
                hour_limit,
                manual=manual,
            ),
            hour_limit,
        )

    day_filters = [
        assessments.c.project_id == project_id,
        assessments.c.created_at > now - day_window,
        assessments.c.created_at <= now,
    ]
    if manual:
        day_filters.append(assessments.c.trigger == AssessmentTrigger.manual.value)
    day_count, day_oldest = conn.execute(
        sa.select(sa.func.count(), sa.func.min(assessments.c.created_at)).where(*day_filters)
    ).one()
    if day_count >= settings.project_assessments_per_day and day_oldest is not None:
        return QuotaDecision(
            "day",
            _quota_resets_at(
                conn,
                project_id,
                now,
                day_window,
                day_count,
                settings.project_assessments_per_day,
                manual=manual,
            ),
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
