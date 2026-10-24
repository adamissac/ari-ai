"""Ask GitHub to redeliver App webhooks that never reached this service.

GitHub does not retry a failed delivery, so a push that arrived while the service was
down (a deploy swaps containers) would never be assessed. On boot, once the API is up,
this lists the App's recent deliveries and redelivers every one whose GUID neither got
a 2xx response nor was recorded in ``webhook_deliveries``. Redelivered events keep their
GUID, so the webhook's dedupe makes running this twice harmless.

Run: ``python -m backend.redeliver`` (deploy/railway/start.sh does it on every boot).
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import sqlalchemy as sa

log = logging.getLogger(__name__)


def missed(deliveries: list[dict[str, Any]], received: set[str]) -> list[int]:
    """Ids to redeliver: the newest attempt of each GUID that never got a 2xx and that we
    never recorded."""
    ok = {d["guid"] for d in deliveries if 200 <= int(d.get("status_code") or 0) < 300}
    newest: dict[str, dict[str, Any]] = {}
    for d in deliveries:
        guid = d["guid"]
        if guid in ok or guid in received:
            continue
        if guid not in newest or d["delivered_at"] > newest[guid]["delivered_at"]:
            newest[guid] = d
    return [int(d["id"]) for d in newest.values()]


def recover(app: Any, received: set[str], *, since: datetime) -> list[int]:
    ids = missed(app.hook_deliveries(since=since), received)
    for delivery_id in ids:
        app.redeliver(delivery_id)
    return ids


def main(api: str = "http://127.0.0.1:8000", hours: int = 24) -> int:
    from backend.db import transaction, webhook_deliveries
    from backend.github import GitHubApp, GitHubNotConfigured

    for _ in range(90):  # the redelivered webhooks need this instance's API to be up
        try:
            if httpx.get(f"{api}/healthz", timeout=2).status_code == 200:
                break
        except httpx.HTTPError:
            pass
        time.sleep(2)
    try:
        app = GitHubApp()
    except GitHubNotConfigured:
        return 0
    since = datetime.now(UTC) - timedelta(hours=hours)
    with transaction() as conn:
        received = set(
            conn.execute(
                sa.select(webhook_deliveries.c.delivery_id).where(
                    webhook_deliveries.c.received_at >= since
                )
            ).scalars()
        )
    ids = recover(app, received, since=since)
    log.warning("requested redelivery of %d missed GitHub webhook(s)", len(ids))
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    raise SystemExit(main())
