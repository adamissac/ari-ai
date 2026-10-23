"""Read-only adaptation of hash-pinned existing live records, with no policy replay."""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
from typing import Any

from shared.evidence import EvidenceRef

from rl_defense.live.contracts import LiveTransition
from rl_defense.live.scenarios import LiveScenario
from rl_defense.research.records import Measurement, ResearchTransition


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def evidence(path: str, sha: str, pointer: str) -> EvidenceRef:
    return EvidenceRef(
        kind="artifact",
        artifact_id=f"art_{sha[:26]}",
        sha256=sha,
        provenance="rl_defense.research@1",
        note=f"{path}#{pointer}",
    )


def adapt(
    t: LiveTransition,
    *,
    source: EvidenceRef,
    dataset_id: str,
    policy: str,
    sc: LiveScenario,
    seed: int,
    index: int,
    current_mask: list[bool] | None = None,
    delegated_blocked: int | None = None,
) -> ResearchTransition:
    o = t.outcome

    def measure(value: float | None, definition: str, reason: str | None = None) -> Measurement:
        return Measurement(
            value=value, evidence=source, definition=definition, unknown_reason=reason
        )

    if t.action != o.action or t.reward != o.reward or t.reward_components != o.reward_components:
        raise ValueError("transition/outcome disagree")
    if t.done != (o.terminated or o.truncated) or o.step != index + 1:
        raise ValueError("transition termination/step mismatch")
    space = {48: "sim", 49: "live_v2", 55: "live_v3"}[len(t.obs)]
    return ResearchTransition(
        dataset_id=dataset_id,
        policy=policy,
        scenario=sc.name,
        scenario_hash=sc.config_hash(),
        split=sc.split,
        seed=seed,
        t=index,
        action_space=space,
        obs=tuple(t.obs),
        action=t.action,
        current_mask=None if current_mask is None else tuple(current_mask),
        next_obs=tuple(t.next_obs),
        next_mask=tuple(t.action_mask),
        terminated=o.terminated,
        truncated=o.truncated,
        attack_active=o.attack_active,
        attack_requests=o.attack_requests,
        compromised_reads=o.compromised_reads,
        benign_requests=o.benign_requests,
        benign_blocked=o.benign_blocked,
        threat_reward=measure(-o.compromised_reads, "negative observed compromised attack reads"),
        benign_cost=measure(
            o.benign_blocked, "defense-denied generator-labelled legitimate requests"
        ),
        legacy_reward=measure(t.reward, "unchanged original scalar reward"),
        delegated_blocked=measure(
            delegated_blocked,
            "defense-denied authorized delegated requests",
            "request-level grant attribution absent" if delegated_blocked is None else None,
        ),
        outcome_evidence=source,
    )


def validate_episodes(rows: list[ResearchTransition]) -> None:
    if not rows:
        raise ValueError("empty dataset")
    groups: dict[tuple, list[ResearchTransition]] = {}
    for r in rows:
        key = (r.policy, r.scenario, r.seed)
        groups.setdefault(key, []).append(r)
    for ts in groups.values():
        ts.sort(key=lambda r: r.t)
        if [r.t for r in ts] != list(range(len(ts))):
            raise ValueError("duplicate/overlapping or missing transition indices")
        if not (ts[-1].terminated or ts[-1].truncated):
            raise ValueError("incomplete episode")
        for a, b in zip(ts, ts[1:], strict=False):
            if a.terminated or a.truncated or a.next_obs != b.obs:
                raise ValueError("broken episode chain")
            if b.current_mask is not None and a.next_mask != b.current_mask:
                raise ValueError("mask chain mismatch")
            if (a.scenario_hash, a.split, a.dataset_id, a.action_space) != (
                b.scenario_hash,
                b.split,
                b.dataset_id,
                b.action_space,
            ):
                raise ValueError("episode provenance changed")


def load_legacy(
    path: Path,
    *,
    expected_sha256: str,
    scenarios: list[LiveScenario],
    policy: str,
    allow_validation: bool = False,
) -> list[ResearchTransition]:
    """Existing episode JSONL(.gz) or flat experience JSONL; never OPE/training.

    Expected SHA must come from the caller's trusted evidence index, not the file itself.
    Split/scenario hashes are checked against explicit configs. No implicit holdout opt-in.
    """
    raw = path.read_bytes()
    if digest(raw) != expected_sha256:
        raise ValueError("source dataset SHA256 mismatch")
    by = {s.name: s for s in scenarios}
    if len(by) != len(scenarios) or not by or any(s.split == "holdout" for s in scenarios):
        raise ValueError("unique explicit train/val scenarios required; holdout forbidden")
    if not allow_validation and any(s.split != "train" for s in scenarios):
        raise ValueError("validation requires analysis-only opt-in")
    payload = gzip.decompress(raw) if path.suffix == ".gz" else raw
    grouped: dict[tuple, list[dict[str, Any]]] = {}
    for line in payload.decode().splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        sc = by[rec["scenario"]]
        if (
            rec.get("split", sc.split) != sc.split
            or rec.get("scenario_hash", sc.config_hash()) != sc.config_hash()
        ):
            raise ValueError("split/scenario hash mismatch")
        if rec.get("policy", policy) != policy:
            raise ValueError("mixed policies")
        key = (sc.name, rec["seed"])
        if "transitions" in rec:
            if key in grouped:
                raise ValueError("duplicate/overlapping episode")
            grouped[key] = rec["transitions"]
        else:
            ts = grouped.setdefault(key, [])
            if rec["t"] != len(ts):
                raise ValueError("flat experiences overlap or are unordered")
            # Metadata is separate from the existing strict transition schema.
            grouped[key].append({k: rec[k] for k in LiveTransition.model_fields})
    rows = []
    for (name, seed), ts in sorted(grouped.items()):
        sc = by[name]
        if len(ts) != sc.horizon or seed not in sc.seeds():
            raise ValueError("episode differs from configured horizon/seeds")
        previous = None
        for i, item in enumerate(ts):
            t = LiveTransition.model_validate(item)
            source = evidence(path.name, expected_sha256, f"{name}/{seed}/transitions/{i}/outcome")
            rows.append(
                adapt(
                    t,
                    source=source,
                    dataset_id=f"legacy_{expected_sha256}",
                    policy=policy,
                    sc=sc,
                    seed=seed,
                    index=i,
                    current_mask=previous,
                )
            )
            previous = t.action_mask
    validate_episodes(rows)
    return rows
