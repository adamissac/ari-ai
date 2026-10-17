"""Reviewed simulation classifications; never executable controls."""

from shared.evidence import EvidenceRef
from shared.rl import DefenseActionName
from shared.standards import DefensiveMapping
from standards.mapping import d3fend_for_rl_action


def defensive_refs(action: DefenseActionName) -> list[DefensiveMapping]:
    evidence = [
        EvidenceRef(
            kind="doc",
            path="standards/standards/data/rules/rl_d3fend.json",
            provenance="rl_defense.standards",
            note=f"Reviewed offline simulator action rule: {action}",
        )
    ]
    return d3fend_for_rl_action(action, evidence=evidence)[0]
