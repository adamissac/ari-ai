"""Impact correlation. Symbol-level impact comes from code-intelligence
(``affected_by_diff``); when it is unavailable we degrade honestly to a
``path_only`` ImpactSet built from the verified webhook's changed paths."""

from __future__ import annotations

from typing import Protocol

from monitoring.normalize import GitHubChange
from shared.intelligence import ImpactResolution, ImpactSet


class ImpactProvider(Protocol):
    """Implemented by code_intelligence (Sarosh). Must be pinned to the exact SHAs."""

    def affected_by_diff(
        self, repo_id: str, base_sha: str | None, head_sha: str, changed_paths: list[str]
    ) -> ImpactSet: ...


def path_only_impact(repo_id: str, change: GitHubChange) -> ImpactSet:
    return ImpactSet(
        repo_id=repo_id,
        base_sha=change.base_sha,
        head_sha=change.head_sha,
        resolution=ImpactResolution.path_only,
        changed_paths=list(change.changed_paths),
    )


def correlate(
    repo_id: str, change: GitHubChange, provider: ImpactProvider | None
) -> tuple[ImpactSet, str | None]:
    """Returns (impact, degradation_note)."""
    if provider is None:
        return path_only_impact(repo_id, change), "code_intelligence unavailable: path-only impact"
    try:
        impact = provider.affected_by_diff(
            repo_id, change.base_sha, change.head_sha, list(change.changed_paths)
        )
    except Exception as exc:  # degrade, never fabricate symbol impact
        return path_only_impact(
            repo_id, change
        ), f"code_intelligence error ({type(exc).__name__}): path-only impact"
    if impact.head_sha != change.head_sha or impact.repo_id != repo_id:
        return path_only_impact(
            repo_id, change
        ), "code_intelligence returned impact for a different SHA; rejected"
    return impact, None
