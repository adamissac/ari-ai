from __future__ import annotations

from types import SimpleNamespace

import pytest

from security_agents.contracts import ErrorCode, PlatformError
from security_agents.intel import host_service
from security_agents.intel.host_service import shared_host_intel


class _Service:
    def __init__(self) -> None:
        self.index_calls: list[tuple[str, str, str]] = []

    def index_repository(self, project_id: str, repo_id: str, commit_sha: str):
        self.index_calls.append((project_id, repo_id, commit_sha))
        return SimpleNamespace(snapshot_id=f"snp_{len(self.index_calls)}")


class _Host:
    project_id = "prj_test"
    repo_id = "rep_test"
    assessment = SimpleNamespace(commit_sha="a" * 40)

    def __init__(self, service: _Service, attachment_results: list[bool]) -> None:
        self.service = service
        self.attachment_results = iter(attachment_results)
        self.attachments: list[object] = []

    def intelligence_service(self, *, include_prefix: str):
        assert include_prefix == ""
        return self.service

    def attach_snapshot(self, ref):
        self.attachments.append(ref)
        return next(self.attachment_results)


class _Adapter:
    def __init__(self, *, service, ref, workspace, path_prefix) -> None:
        self.service = service
        self.ref = ref
        self.workspace = workspace
        self.path_prefix = path_prefix
        self.verified = False

    def verify_workspace(self) -> None:
        self.verified = True


@pytest.fixture
def fake_adapter(monkeypatch):
    monkeypatch.setattr(host_service, "CodeIntelligenceAdapter", _Adapter)


def _snapshot(tmp_path):
    return SimpleNamespace(pinned_by="git", root=tmp_path)


def test_shared_host_intel_reindexes_when_attachment_loses_snapshot_race(
    tmp_path, fake_adapter
) -> None:
    service = _Service()
    host = _Host(service, [False, True])

    adapter = shared_host_intel(host, _snapshot(tmp_path), [{"repo_id": host.repo_id}])

    assert len(service.index_calls) == 2
    assert len(host.attachments) == 2
    assert adapter is not None and adapter.ref is host.attachments[1]
    assert adapter.verified


def test_shared_host_intel_raises_not_ready_after_second_attachment_failure(
    tmp_path, fake_adapter
) -> None:
    service = _Service()
    host = _Host(service, [False, False])

    with pytest.raises(PlatformError) as exc:
        shared_host_intel(host, _snapshot(tmp_path), [{"repo_id": host.repo_id}])

    assert exc.value.code is ErrorCode.SNAPSHOT_NOT_READY
    assert len(service.index_calls) == 2
    assert len(host.attachments) == 2
