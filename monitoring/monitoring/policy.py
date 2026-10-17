"""Reassessment trigger policy (docs/10 "Trigger policy"). Pure and deterministic.

Monitoring never widens scope: without an active AuthorizedScope the decision is
``blocked_no_scope`` and nothing runs.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from functools import lru_cache

from shared.intelligence import ImpactResolution, ImpactSet
from shared.monitoring import ReassessmentScope
from shared.tenancy import TriggerPolicy


class Action(StrEnum):
    assess = "assess"
    record_only = "record_only"
    blocked_no_scope = "blocked_no_scope"
    coalesced = "coalesced"


@dataclass(frozen=True)
class Decision:
    action: Action
    reason: str
    scope: ReassessmentScope | None = None
    targets: tuple[str, ...] = field(default_factory=tuple)
    regression_finding_ids: tuple[str, ...] = field(default_factory=tuple)


@lru_cache(maxsize=256)
def _glob_re(glob: str) -> re.Pattern[str]:
    out, i = [], 0
    while i < len(glob):
        if glob.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif glob.startswith("**", i):
            out.append(".*")
            i += 2
        elif glob[i] == "*":
            out.append("[^/]*")
            i += 1
        elif glob[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(glob[i]))
            i += 1
    return re.compile("^" + "".join(out) + "$")


def matches_any(path: str, globs: Iterable[str]) -> bool:
    return any(_glob_re(g).match(path) for g in globs)


def decide(
    impact: ImpactSet,
    *,
    policy: TriggerPolicy,
    paths_complete: bool,
    has_active_scope: bool,
    verified_finding_paths: Mapping[str, Iterable[str]],
    seconds_since_last_monitoring_assessment: float | None,
    open_monitoring_assessment: bool,
) -> Decision:
    if not policy.enabled:
        return Decision(Action.record_only, "monitoring disabled for project")

    changed = list(impact.changed_paths)
    code_paths = [p for p in changed if not matches_any(p, policy.ignore_paths_only)]
    if paths_complete and changed and not code_paths:
        return Decision(Action.record_only, "only tests/docs changed")
    if paths_complete and not changed and impact.resolution is ImpactResolution.path_only:
        return Decision(Action.record_only, "no file changes in range")

    # Verified fixes whose code was touched need their regression check re-run.
    changed_set = set(changed)
    regress = tuple(
        sorted(fid for fid, paths in verified_finding_paths.items() if changed_set & set(paths))
    ) + tuple(sorted(set(impact.findings) - set(verified_finding_paths)))

    if not has_active_scope:
        return Decision(
            Action.blocked_no_scope,
            "no active AuthorizedScope covers this repository",
            regression_finding_ids=regress,
        )
    if open_monitoring_assessment:
        return Decision(
            Action.coalesced, "a monitoring-triggered assessment for this repo is still running"
        )
    if (
        seconds_since_last_monitoring_assessment is not None
        and seconds_since_last_monitoring_assessment < policy.min_interval_s
    ):
        return Decision(
            Action.coalesced,
            f"within {policy.min_interval_s}s coalescing window of the previous reassessment",
        )

    if not paths_complete:
        return Decision(
            Action.assess,
            "changed-path list incomplete; full reassessment",
            ReassessmentScope.full,
            regression_finding_ids=regress,
        )
    non_regression = [
        p
        for p in code_paths
        if not any(p in set(paths) for paths in verified_finding_paths.values())
    ]
    if regress and not non_regression:
        return Decision(
            Action.assess,
            "change touches code of verified findings; re-run regression checks",
            ReassessmentScope.regression_only,
            targets=regress,
            regression_finding_ids=regress,
        )
    targets = tuple(impact.symbols) or tuple(sorted(code_paths))
    return Decision(
        Action.assess,
        f"{len(code_paths)} code path(s) changed under active scope",
        ReassessmentScope.targeted,
        targets=targets[:200],
        regression_finding_ids=regress,
    )
