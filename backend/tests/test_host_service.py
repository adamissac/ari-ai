from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from security_agents.contracts import ErrorCode, PlatformError
from security_agents.intel import host_service
from security_agents.intel.host_service import shared_host_intel


class _Service:
    def __init__(self) -> None:
        self.index_calls: list[tuple[str, str, str]] = []

    def index_repository(self, project_id: str, repo_id: str, commit_sha: str) -> SimpleNamespace:
        self.index_calls.append((project_id, repo_id, commit_sha))
        return SimpleNamespace(snapshot_id=f"snp_{len(self.index_calls)}")


class _Host:
    project_id: str = "prj_test"
    repo_id: str = "rep_test"
    assessment: SimpleNamespace = SimpleNamespace(commit_sha="a" * 40)

    def __init__(self, service: _Service, attachment_results: list[bool]) -> None:
        self.service = service
        self.attachment_results = iter(attachment_results)
        self.attachments: list[object] = []

    def intelligence_service(self, *, include_prefix: str) -> _Service:
        assert include_prefix == ""
        return self.service

    def attach_snapshot(self, ref: Any) -> bool:
        self.attachments.append(ref)
        return next(self.attachment_results)


class _Adapter:
    def __init__(self, *, service: _Service, ref: Any, workspace: Path, path_prefix: str) -> None:
        self.service: _Service = service
        self.ref: Any = ref
        self.workspace: Path = workspace
        self.path_prefix: str = path_prefix
        self.verified: bool = False

    def verify_workspace(self) -> None:
        self.verified = True


@pytest.fixture
def fake_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(host_service, "CodeIntelligenceAdapter", _Adapter)


def _snapshot(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(pinned_by="git", root=tmp_path)


def test_shared_host_intel_reindexes_when_attachment_loses_snapshot_race(
    tmp_path: Path, fake_adapter: None
) -> None:
    service = _Service()
    host = _Host(service, [False, True])

    adapter = shared_host_intel(host, _snapshot(tmp_path), [{"repo_id": host.repo_id}])

    assert len(service.index_calls) == 2
    assert len(host.attachments) == 2
    assert adapter is not None and adapter.ref is host.attachments[1]
    assert adapter.verified


def test_shared_host_intel_raises_not_ready_after_second_attachment_failure(
    tmp_path: Path, fake_adapter: None
) -> None:
    service = _Service()
    host = _Host(service, [False, False])

    with pytest.raises(PlatformError) as exc:
        shared_host_intel(host, _snapshot(tmp_path), [{"repo_id": host.repo_id}])

    assert exc.value.code is ErrorCode.SNAPSHOT_NOT_READY
    assert len(service.index_calls) == 2
    assert len(host.attachments) == 2
