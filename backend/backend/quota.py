"""Shared rolling-window review quotas for project assessment starts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Literal

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.db import assessments, projects
from backend.services import project_settings
from backend.settings import get_settings
from shared.base import utcnow
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
    # Check-then-insert: locking the project row makes concurrent starts for one project
    # wait here until the caller's insert commits, so counts cannot overshoot. It is the
    # same lock auto_commits.assess_commit takes first, so every start path locks the
    # project before the repository row (create_assessment) and none can deadlock.
    # shortcut: the global spend cap is only as fresh as recorded usage, so in-flight
    # runs in other projects can still overshoot it; it is a cost bound, not a quota.
    conn.execute(sa.select(projects.c.id).where(projects.c.id == project_id).with_for_update())
    # The caller's `now` predates any wait for the lock; a start that committed meanwhile
    # carries a later created_at and must still count.
    now = max(now, utcnow())
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
    spend_filters = (
        assessments.c.created_at > now - day_window,
        assessments.c.created_at <= now,
        positive_usage > 0,
    )
    spent, spend_oldest = conn.execute(
        sa.select(usage_usd, sa.func.min(assessments.c.created_at)).where(
            *spend_filters,
        )
    ).one()
    if float(spent) >= settings.assessments_usd_per_day and spend_oldest is not None:
        cap = sa.literal(Decimal(str(settings.assessments_usd_per_day)), sa.Numeric)
        spend_window = (
            sa.select(
                assessments.c.created_at,
                sa.func.sum(positive_usage)
                .over(order_by=(assessments.c.created_at, assessments.c.id), rows=(None, 0))
                .label("expired"),
                sa.func.sum(positive_usage).over().label("total"),
            )
            .where(*spend_filters)
            .subquery()
        )
        reset_from = conn.execute(
            sa.select(spend_window.c.created_at)
            .where(spend_window.c.total - spend_window.c.expired < cap)
            .order_by(spend_window.c.created_at)
            .limit(1)
        ).scalar_one_or_none()
        return QuotaDecision("spend", (reset_from or spend_oldest) + day_window)

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
