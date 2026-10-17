"""GET /assessments/{id}/events/log pages by seq with a real next_cursor (Adam's
20261017T152510Z ask): a full page used to return next_cursor=null, hiding later events."""

from __future__ import annotations

from helpers import setup_project

from backend.db import transaction
from backend.host import emit_event
from shared.events import StreamEventType


def test_event_log_pages_through_every_event(client_factory) -> None:
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)
    asm = alice.post(
        f"/api/v1/projects/{ids['project']}/assessments",
        json={"scope_id": ids["scope"], "repo_id": ids["repo"], "commit_sha": "b" * 40},
    ).json()["assessment"]["id"]
    with transaction() as conn:
        for i in range(7):
            emit_event(conn, asm, StreamEventType.progress, f"step {i}")
    url = f"/api/v1/assessments/{asm}/events/log"
    total = alice.get(url).json()
    assert total["next_cursor"] is None  # everything fits in one default page
    expected = [e["seq"] for e in total["items"]]
    assert len(expected) >= 7 and expected == sorted(expected)

    seen, after, pages = [], 0, 0
    while True:
        page = alice.get(url, params={"after": after, "limit": 3}).json()
        pages += 1
        seen += [e["seq"] for e in page["items"]]
        if page["next_cursor"] is None:
            break
        assert len(page["items"]) == 3
        after = int(page["next_cursor"])
        assert after == page["items"][-1]["seq"]
    assert seen == expected and pages == -(-len(expected) // 3) + (len(expected) % 3 == 0)

    assert alice.get(url, params={"limit": 0}).status_code == 422
    assert alice.get(url, params={"limit": 501}).status_code == 422
    assert client_factory("eve").get(url).status_code == 404
