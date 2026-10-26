"""Fail-closed comparisons for the runtime pytest audit artifact."""

from __future__ import annotations

from collections import Counter
from typing import Any

_OUTCOMES = {"passed", "failed", "error", "skipped", "xfailed", "xpassed"}
_HOOK_FIELDS = ("hook", "module", "qualname", "file", "code_sha256")


def _validated(audit: dict[str, Any] | None) -> dict[str, Any] | None:
    if (
        not isinstance(audit, dict)
        or type(audit.get("version")) is not int
        or audit.get("version") != 1
        or audit.get("complete") is not True
    ):
        return None
    phases = audit.get("phases")
    nodeids = audit.get("nodeids")
    outcomes = audit.get("outcomes")
    if (
        not isinstance(phases, dict)
        or not all(isinstance(phases.get(phase), list) for phase in ("collection", "final"))
        or not isinstance(nodeids, list)
        or not all(isinstance(nodeid, str) for nodeid in nodeids)
        or not isinstance(outcomes, dict)
        or not all(
            isinstance(nodeid, str) and isinstance(outcome, str) and outcome in _OUTCOMES
            for nodeid, outcome in outcomes.items()
        )
    ):
        return None

    hooks: dict[str, list[tuple[Any, ...]]] = {}
    for phase in ("collection", "final"):
        parsed: list[tuple[Any, ...]] = []
        for entry in phases[phase]:
            if not isinstance(entry, dict) or not all(
                isinstance(entry.get(field), str) for field in _HOOK_FIELDS
            ):
                return None
            flags = entry.get("flags")
            if not isinstance(flags, list) or not all(isinstance(flag, str) for flag in flags):
                return None
            parsed.append(
                (
                    entry["hook"],
                    entry["module"],
                    entry["qualname"],
                    entry["file"],
                    tuple(sorted(flags)),
                    entry["code_sha256"],
                )
            )
        hooks[phase] = parsed
    return {"hooks": hooks, "nodeids": set(nodeids), "outcomes": outcomes}


def _hook_labels(counter: Counter[tuple[Any, ...]], limit: int = 10) -> str:
    entries = list(counter.items())
    labels = [
        f"{hook[0]}:{hook[2]}#{hook[5][:12]}" + (f" x{count}" if count > 1 else "")
        for hook, count in entries[:limit]
    ]
    remaining = len(entries) - len(labels)
    if remaining:
        labels.append(f"{remaining} more")
    return ", ".join(labels)


def compare_pytest_audits(baseline: dict | None, patched: dict | None) -> list[str]:
    """Return runtime findings; absent or malformed evidence always fails closed."""
    base = _validated(baseline)
    if base is None:
        return ["baseline pytest audit missing, malformed, or incomplete"]
    current = _validated(patched)
    if current is None:
        return ["patched pytest audit missing, malformed, or incomplete"]

    findings: list[str] = []
    for phase in ("collection", "final"):
        baseline_hooks = Counter(base["hooks"][phase])
        patched_hooks = Counter(current["hooks"][phase])
        removed = baseline_hooks - patched_hooks
        added = patched_hooks - baseline_hooks
        if removed:
            findings.append(f"{phase} hook removed or changed: {_hook_labels(removed)}")
        if added:
            findings.append(f"{phase} hook added or changed: {_hook_labels(added)}")

    missing_nodeids = sorted(base["nodeids"] - current["nodeids"])
    if missing_nodeids:
        listed = missing_nodeids[:20]
        suffix = f", {len(missing_nodeids) - len(listed)} more" if len(missing_nodeids) > len(listed) else ""
        findings.append(f"protected tests not collected: {', '.join(listed)}{suffix}")

    for nodeid in sorted(base["nodeids"]):
        if base["outcomes"].get(nodeid) != "passed":
            continue
        outcome = current["outcomes"].get(nodeid, "missing")
        if outcome not in {"passed", "failed", "error"}:
            findings.append(f"test no longer executes: {nodeid} -> {outcome}")
    return findings
