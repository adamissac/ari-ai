"""Cross-owner integration: Sarosh's IntelligenceService (feat/sarosh/code-intelligence)
indexes two real commits of Adam's examples/payments-lite target, persisting through
backend.intel_store.PostgresPayloadStore. A signed push webhook then gets SYMBOL-level
impact from the real indexes (no path-only fallback). Skips if code_intelligence is
not installed in this environment."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ci_api = pytest.importorskip("code_intelligence.api")
ci_persistence = pytest.importorskip("code_intelligence.persistence")

from helpers import REPO, post_webhook, push_payload, setup_project  # noqa: E402

from backend import worker  # noqa: E402
from backend.intel_store import PostgresPayloadStore  # noqa: E402

TARGET = Path(__file__).resolve().parents[2] / "examples" / "payments-lite" / "target"
_SERVICE: list[object] = []


def service_factory() -> object:
    """Referenced by CODE_INTELLIGENCE_FACTORY during this test only."""
    return _SERVICE[0]


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(
        [
            "git",
            "-C",
            str(root),
            "-c",
            "core.hooksPath=/dev/null",
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@example.invalid",
            "-c",
            "commit.gpgsign=false",
            *args,
        ],
        text=True,
    ).strip()


@pytest.fixture
def two_commits(tmp_path: Path) -> tuple[Path, str, str, str]:
    if not TARGET.exists():
        pytest.skip("examples/payments-lite/target not present")
    root = tmp_path / "payments-lite"
    shutil.copytree(
        TARGET, root, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache")
    )
    _git(root, "init", "-q")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "base")
    base = _git(root, "rev-parse", "HEAD")
    changed = root / "payments_lite" / "app.py"
    assert changed.exists(), "payments-lite route module not found"
    changed.write_text(changed.read_text() + "\n\ndef audit_marker() -> int:\n    return 1\n")
    _git(root, "commit", "-qam", "change payments")
    head = _git(root, "rev-parse", "HEAD")
    return root, base, head, str(changed.relative_to(root))


def test_symbol_impact_from_real_indexes(client_factory, settings_override, two_commits) -> None:
    root, base, head, changed_path = two_commits
    alice, bob = client_factory("alice"), client_factory("bob")
    ids = setup_project(alice, bob)
    store = ci_persistence.PayloadIndexStore(PostgresPayloadStore())
    binding = ci_api.RepositoryBinding(
        project_id=ids["project"], repo_id=ids["repo"], full_name=REPO, local_path=root
    )
    svc = ci_api.IntelligenceService(store, [binding])
    ref_base = svc.index_repository(ids["project"], ids["repo"], base)
    ref_head = svc.index_repository(ids["project"], ids["repo"], head)
    assert ref_base.commit_sha == base and ref_head.commit_sha == head

    # Durable: a brand-new service over the same database finds the same snapshot.
    again = ci_api.IntelligenceService(
        ci_persistence.PayloadIndexStore(PostgresPayloadStore()), [binding]
    )
    assert again.index_repository(ids["project"], ids["repo"], head) == ref_head
    snap = alice.get(f"/api/v1/snapshots/{ref_head.snapshot_id}").json()
    assert snap["status"] == "ready" and snap["stats"]["symbols"] > 0

    impact = again.affected_by_diff(ids["repo"], base, head)
    assert (
        impact.resolution.value == "symbol"
        and changed_path in impact.changed_paths
        and impact.symbols
    )

    _SERVICE[:] = [again]
    settings_override(code_intelligence_factory="test_intel_integration:service_factory")
    post_webhook(alice, push_payload([changed_path], head=head, base=base))
    worker.drain(kinds=["process_github_delivery"])
    ev = alice.get(f"/api/v1/projects/{ids['project']}/events").json()["items"][0]
    assert ev["impact"]["resolution"] == "symbol"
    assert ev["impact"]["head_snapshot_id"] == ref_head.snapshot_id
    assert set(ev["impact"]["symbols"]) == set(impact.symbols)
    rrq = alice.get(f"/api/v1/projects/{ids['project']}/reassessments").json()["items"][0]
    assert rrq["status"] == "started" and set(rrq["targets"]) <= set(impact.symbols)
