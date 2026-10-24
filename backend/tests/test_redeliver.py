"""Missed GitHub webhooks are redelivered on boot (GitHub never retries them itself)."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx

from backend.github import GitHubApp
from backend.redeliver import missed, recover
from backend.settings import Settings


def _app_with_client(client: httpx.Client) -> GitHubApp:
    app = GitHubApp.__new__(GitHubApp)
    app.settings = Settings(github_app_id="1")
    app._client = client
    app._tokens = {}
    app._app_jwt = lambda: "app-jwt"  # type: ignore[method-assign]
    return app


def _d(id: int, guid: str, status: int, at: str) -> dict:
    return {"id": id, "guid": guid, "status_code": status, "delivered_at": at, "event": "push"}


def test_only_never_delivered_unrecorded_guids_are_redelivered_once() -> None:
    deliveries = [
        _d(1, "ok", 200, "2026-10-24T06:00:00Z"),
        _d(2, "down", 502, "2026-10-24T06:01:00Z"),
        _d(3, "down", 0, "2026-10-24T06:02:00Z"),  # retried, still failed: newest attempt
        _d(4, "later-ok", 503, "2026-10-24T06:03:00Z"),
        _d(5, "later-ok", 202, "2026-10-24T06:04:00Z"),
        _d(6, "recorded", 500, "2026-10-24T06:05:00Z"),  # GitHub saw a timeout, we stored it
    ]
    assert missed(deliveries, {"recorded"}) == [3]


def test_recover_pages_back_to_the_cutoff_and_posts_attempts() -> None:
    posted: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer app-jwt"
        if request.method == "POST":
            posted.append(request.url.path)
            return httpx.Response(202)
        if request.url.params.get("cursor") == "p2":
            return httpx.Response(200, json=[_d(8, "old", 502, "2026-10-23T01:00:00Z")])
        return httpx.Response(
            200,
            json=[_d(9, "new", 502, "2026-10-24T06:00:00Z")],
            headers={"Link": '<https://api.github.com/app/hook/deliveries?cursor=p2>; rel="next"'},
        )

    app = _app_with_client(
        httpx.Client(base_url="https://api.github.com", transport=httpx.MockTransport(handler))
    )
    ids = recover(app, set(), since=datetime(2026, 10, 24, tzinfo=UTC))
    assert ids == [9]  # the delivery before the cutoff is left alone
    assert posted == ["/app/hook/deliveries/9/attempts"]
