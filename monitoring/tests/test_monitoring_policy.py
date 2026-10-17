from __future__ import annotations

from monitoring.api import Action, Ignored, decide, matches_any, normalize_github, path_only_impact
from shared.monitoring import ReassessmentScope
from shared.tenancy import TriggerPolicy

HEAD, BASE = "b" * 40, "a" * 40


def push(paths: list[str], *, commits: int = 1, **over: object) -> dict:
    payload = {
        "ref": "refs/heads/main",
        "before": BASE,
        "after": HEAD,
        "forced": False,
        "deleted": False,
        "repository": {"full_name": "acme/payments-lite"},
        "sender": {"login": "dev"},
        "head_commit": {"timestamp": "2026-10-17T01:02:03Z"},
        "commits": [{"added": [], "modified": paths, "removed": []}] + [{}] * (commits - 1),
    }
    payload.update(over)
    return payload


def test_push_normalizes_paths_and_rejects_traversal() -> None:
    change = normalize_github(
        "push", push(["app/invoices.py", "../etc/passwd", "/abs", "tests/t.py"])
    )
    assert not isinstance(change, Ignored)
    assert change.changed_paths == ("app/invoices.py", "tests/t.py")
    assert change.paths_complete and change.base_sha == BASE and change.head_sha == HEAD
    assert change.occurred_at.isoformat() == "2026-10-17T01:02:03+00:00"


def test_push_ignores_deletes_tags_and_bad_shas() -> None:
    assert isinstance(normalize_github("push", push([], deleted=True)), Ignored)
    assert isinstance(normalize_github("push", push([], ref="refs/tags/v1")), Ignored)
    assert isinstance(normalize_github("push", push([], after="not-a-sha")), Ignored)
    assert isinstance(normalize_github("ping", {"zen": "hi"}), Ignored)
    assert isinstance(normalize_github("issues", push([])), Ignored)


def test_truncated_push_is_marked_incomplete() -> None:
    change = normalize_github("push", push(["a.py"], commits=20))
    assert not isinstance(change, Ignored) and not change.paths_complete


def test_pull_request_keeps_intent_as_capped_text() -> None:
    payload = {
        "action": "synchronize",
        "number": 7,
        "repository": {"full_name": "acme/payments-lite"},
        "pull_request": {
            "title": "Speed up invoices",
            "body": "x" * 50_000,
            "head": {"sha": HEAD, "ref": "feat"},
            "base": {"sha": BASE, "ref": "main"},
        },
    }
    change = normalize_github("pull_request", payload)
    assert not isinstance(change, Ignored)
    assert change.pr_number == 7 and len(change.pr_body) == 20_000 and not change.paths_complete
    assert isinstance(normalize_github("pull_request", {**payload, "action": "closed"}), Ignored)


def test_globs() -> None:
    globs = ["tests/**", "docs/**", "**/*.md"]
    assert matches_any("tests/unit/test_a.py", globs)
    assert matches_any("README.md", globs) and matches_any("app/notes/x.md", globs)
    assert not matches_any("app/invoices.py", globs)


def _decide(paths: list[str], **kw: object):
    change = normalize_github("push", push(paths))
    assert not isinstance(change, Ignored)
    args = dict(
        policy=TriggerPolicy(),
        paths_complete=change.paths_complete,
        has_active_scope=True,
        verified_finding_paths={},
        seconds_since_last_monitoring_assessment=None,
        open_monitoring_assessment=False,
    )
    args.update(kw)
    return decide(path_only_impact("rep_01JFIXTURE0000000000000REP", change), **args)


def test_policy_table() -> None:
    assert _decide(["tests/test_x.py", "docs/a.md"]).action is Action.record_only
    d = _decide(["app/invoices.py"])
    assert d.action is Action.assess and d.scope is ReassessmentScope.targeted
    assert d.targets == ("app/invoices.py",)
    assert _decide(["app/invoices.py"], has_active_scope=False).action is Action.blocked_no_scope
    assert _decide(["app/x.py"], open_monitoring_assessment=True).action is Action.coalesced
    assert (
        _decide(["app/x.py"], seconds_since_last_monitoring_assessment=30).action
        is Action.coalesced
    )
    assert (
        _decide(["app/x.py"], seconds_since_last_monitoring_assessment=3600).action is Action.assess
    )
    reg = _decide(["app/invoices.py"], verified_finding_paths={"fnd_1": ["app/invoices.py"]})
    assert reg.scope is ReassessmentScope.regression_only and reg.targets == ("fnd_1",)
    mixed = _decide(
        ["app/invoices.py", "app/users.py"], verified_finding_paths={"fnd_1": ["app/invoices.py"]}
    )
    assert mixed.scope is ReassessmentScope.targeted and mixed.regression_finding_ids == ("fnd_1",)
    assert _decide(["app/x.py"], paths_complete=False).scope is ReassessmentScope.full
    assert _decide(["app/x.py"], policy=TriggerPolicy(enabled=False)).action is Action.record_only
