"""Public interface of the monitoring package (pure logic; persistence lives in backend)."""

from monitoring.impact import ImpactProvider, correlate, path_only_impact
from monitoring.normalize import GitHubChange, Ignored, normalize_github, repo_full_name
from monitoring.policy import Action, Decision, decide, matches_any
from monitoring.runtime import ANOMALY_EVENT_THRESHOLD, score_window

__all__ = [
    "ANOMALY_EVENT_THRESHOLD",
    "Action",
    "Decision",
    "GitHubChange",
    "Ignored",
    "ImpactProvider",
    "correlate",
    "decide",
    "matches_any",
    "normalize_github",
    "path_only_impact",
    "repo_full_name",
    "score_window",
]
