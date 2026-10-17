"""Normalize verified GitHub webhook payloads into a minimal, typed change record.

Payloads are untrusted: only the fields below are read, every string is length
capped, SHAs are validated, and nothing here is ever passed raw to an LLM.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

ZERO_SHA = "0" * 40
_SHA = re.compile(r"^[0-9a-f]{40}$")
MAX_PATHS = 3000
PR_ACTIONS = {"opened", "synchronize", "reopened", "ready_for_review", "edited"}
# GitHub truncates push payloads to 20 commits; beyond that the path list is partial.
PUSH_COMMIT_CAP = 20


@dataclass(frozen=True)
class GitHubChange:
    event: str  # "push" | "pull_request"
    repo_full_name: str
    ref: str | None
    base_sha: str | None
    head_sha: str
    changed_paths: tuple[str, ...]
    paths_complete: bool
    occurred_at: datetime
    sender: str | None = None
    pr_number: int | None = None
    pr_action: str | None = None
    pr_title: str = ""
    pr_body: str = ""
    pr_base_ref: str | None = None
    forced: bool = False
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Ignored:
    reason: str
    repo_full_name: str | None = None


def _s(value: Any, cap: int = 500) -> str:
    return value[:cap] if isinstance(value, str) else ""


def _sha(value: Any) -> str | None:
    return value if isinstance(value, str) and _SHA.match(value) and value != ZERO_SHA else None


def _ts(value: Any) -> datetime:
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt.astimezone(UTC) if dt.tzinfo else dt.replace(tzinfo=UTC)
        except ValueError:
            pass
    if isinstance(value, int | float):
        return datetime.fromtimestamp(value, UTC)
    return datetime.now(UTC)


def _clean_path(p: Any) -> str | None:
    if not isinstance(p, str) or not p or len(p) > 1024:
        return None
    if p.startswith("/") or "\\" in p or "\x00" in p or ".." in p.split("/"):
        return None
    return p


def repo_full_name(payload: dict[str, Any]) -> str | None:
    repo = payload.get("repository")
    name = repo.get("full_name") if isinstance(repo, dict) else None
    return (
        name
        if isinstance(name, str) and re.match(r"^[A-Za-z0-9_.\-]+/[A-Za-z0-9_.\-]+$", name)
        else None
    )


def normalize_github(event_name: str, payload: dict[str, Any]) -> GitHubChange | Ignored:
    name = repo_full_name(payload)
    if event_name == "ping":
        return Ignored("ping", name)
    if name is None:
        return Ignored("payload has no valid repository.full_name")
    sender = (
        payload.get("sender", {}).get("login") if isinstance(payload.get("sender"), dict) else None
    )
    if event_name == "push":
        return _push(payload, name, _s(sender, 80) or None)
    if event_name == "pull_request":
        return _pull_request(payload, name, _s(sender, 80) or None)
    return Ignored(f"unsupported event type {event_name!r}", name)


def _push(payload: dict[str, Any], name: str, sender: str | None) -> GitHubChange | Ignored:
    if payload.get("deleted") or payload.get("after") == ZERO_SHA:
        return Ignored("branch or tag deletion", name)
    head = _sha(payload.get("after"))
    if head is None:
        return Ignored("push without a valid head SHA", name)
    ref = _s(payload.get("ref"), 255) or None
    if ref and not ref.startswith("refs/heads/"):
        return Ignored(f"non-branch ref {ref}", name)
    commits = payload.get("commits") if isinstance(payload.get("commits"), list) else []
    paths: set[str] = set()
    for c in commits[:PUSH_COMMIT_CAP]:
        if not isinstance(c, dict):
            continue
        for key in ("added", "modified", "removed"):
            for p in c.get(key) or []:
                cp = _clean_path(p)
                if cp:
                    paths.add(cp)
    complete = len(commits) < PUSH_COMMIT_CAP and len(paths) <= MAX_PATHS and bool(commits)
    notes = []
    if not commits:
        notes.append("push payload lists no commits (e.g. force-push or new branch)")
    if len(commits) >= PUSH_COMMIT_CAP:
        notes.append("push payload truncated at 20 commits; path list partial")
    head_commit = payload.get("head_commit") if isinstance(payload.get("head_commit"), dict) else {}
    return GitHubChange(
        event="push",
        repo_full_name=name,
        ref=ref,
        base_sha=_sha(payload.get("before")),
        head_sha=head,
        changed_paths=tuple(sorted(paths)[:MAX_PATHS]),
        paths_complete=complete,
        occurred_at=_ts(head_commit.get("timestamp")),
        sender=sender,
        forced=bool(payload.get("forced")),
        notes=tuple(notes),
    )


def _pull_request(payload: dict[str, Any], name: str, sender: str | None) -> GitHubChange | Ignored:
    action = _s(payload.get("action"), 40)
    if action not in PR_ACTIONS:
        return Ignored(f"pull_request action {action!r} does not change code", name)
    pr = payload.get("pull_request") if isinstance(payload.get("pull_request"), dict) else {}
    head = _sha((pr.get("head") or {}).get("sha"))
    if head is None:
        return Ignored("pull_request without a valid head SHA", name)
    number = payload.get("number") if isinstance(payload.get("number"), int) else pr.get("number")
    return GitHubChange(
        event="pull_request",
        repo_full_name=name,
        ref=_s((pr.get("head") or {}).get("ref"), 255) or None,
        base_sha=_sha((pr.get("base") or {}).get("sha")),
        head_sha=head,
        changed_paths=(),
        paths_complete=False,
        occurred_at=_ts(pr.get("updated_at")),
        sender=sender,
        pr_number=number if isinstance(number, int) and number > 0 else None,
        pr_action=action,
        pr_title=_s(pr.get("title"), 500),
        pr_body=_s(pr.get("body"), 20_000),
        pr_base_ref=_s((pr.get("base") or {}).get("ref"), 255) or None,
        notes=("pull_request payload carries no file list; fetch compare(base, head)",),
    )
