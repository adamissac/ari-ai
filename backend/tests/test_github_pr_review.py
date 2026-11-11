from __future__ import annotations

import json

import httpx

from backend.github import GitHubApp


def test_post_pull_request_review_posts_comment_without_inline_comments():
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"id": 1})

    app = object.__new__(GitHubApp)
    app._client = httpx.Client(
        base_url="https://api.github.com", transport=httpx.MockTransport(respond)
    )
    app.installation_token = lambda *_args, **_kwargs: "installation-token"
    app.post_pull_request_review(99, "acme/payments-lite", 7, "Ari security review")

    assert len(requests) == 1
    request = requests[0]
    assert request.method == "POST"
    assert request.url.path == "/repos/acme/payments-lite/pulls/7/reviews"
    assert request.headers["Authorization"] == "Bearer installation-token"
    assert json.loads(request.content) == {
        "event": "COMMENT",
        "body": "Ari security review",
    }
    app._client.close()


def _app(respond) -> GitHubApp:
    app = object.__new__(GitHubApp)
    app._client = httpx.Client(
        base_url="https://api.github.com", transport=httpx.MockTransport(respond)
    )
    app.installation_token = lambda *_args, **_kwargs: "installation-token"
    return app


def test_review_with_inline_comments_is_anchored_to_the_assessed_commit():
    bodies: list[dict] = []

    def respond(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json={"id": 1})

    comments = [{"path": "app.py", "line": 7, "side": "RIGHT", "body": "note"}]
    app = _app(respond)
    app.post_pull_request_review(99, "acme/payments-lite", 7, "summary", comments, "abc123")
    assert bodies == [
        {"event": "COMMENT", "body": "summary", "comments": comments, "commit_id": "abc123"}
    ]
    app._client.close()


def test_rejected_inline_anchor_still_posts_the_summary():
    bodies: list[dict] = []

    def respond(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return httpx.Response(422 if "comments" in bodies[-1] else 200, json={})

    app = _app(respond)
    app.post_pull_request_review(
        99, "acme/payments-lite", 7, "summary", [{"path": "a.py", "line": 1, "body": "x"}], "abc"
    )
    assert [("comments" in b) for b in bodies] == [True, False]
    app._client.close()
