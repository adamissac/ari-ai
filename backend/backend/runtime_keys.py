"""Identity of one runtime ingest window and its anomaly event, per application."""

from __future__ import annotations

from datetime import datetime


def runtime_event_key(
    source: str, application_id: str | None, route: str, window_end: datetime
) -> str:
    return f"runtime:{source}:{application_id or '-'}:{route}:{window_end.isoformat()}"[:200]
