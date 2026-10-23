"""Stage2 schema/replay/provenance preparation. No optimizer or checkpoint writer."""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from collections import deque
from dataclasses import asdict
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any, Literal

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict, Field, model_validator
from shared.evidence import EvidenceRef

from rl_defense.research.resource.baselines import Policy, action
from rl_defense.research.resource.env import ACTION_VERSION, OBS_DIM, OBS_VERSION, ResourceEnv
from rl_defense.research.resource.service import Config, Window

COST_NAMES = (
    "legitimate_rate_denials",
    "legitimate_capacity_denials",
    "legitimate_timeouts",
    "legitimate_latency_sum",
    "applications",
    "active_ticks",
    "overhead_units",
)


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, allow_inf_nan=False)


class Costs(Strict):
    legitimate_rate_denials: int = Field(ge=0)
    legitimate_capacity_denials: int = Field(ge=0)
    legitimate_timeouts: int = Field(ge=0)
    legitimate_latency_sum: int = Field(ge=0)
    applications: int = Field(ge=0, le=1)
    active_ticks: int = Field(ge=0)
    overhead_units: int = Field(ge=0, le=1)


class Transition(Strict):
    schema_version: Literal["resource-experience/0.1"] = "resource-experience/0.1"
    purpose: Literal["unit_instrumentation"] = "unit_instrumentation"
    observation_version: Literal["resource-observation/0.1"] = OBS_VERSION
    action_version: Literal["resource-actions/0.1"] = ACTION_VERSION
    environment_version: Literal["resource-queue/0.1"] = "resource-queue/0.1"
    config_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    profile: Literal["budgeted", "persistent_static"]
    episode: str
    seed: int = Field(ge=0)
    step: int = Field(ge=0)
    obs: tuple[float, ...]
    mask: tuple[bool, ...]
    proposed: int = Field(ge=0, le=2)
    applied: int = Field(ge=0, le=2)
    reward: float = Field(le=0)
    costs: Costs
    next_obs: tuple[float, ...]
    next_mask: tuple[bool, ...]
    terminated: bool
    truncated: bool
    before_cutoff: int = Field(ge=0)
    action_seq: int = Field(ge=1)
    next_cutoff: int = Field(ge=2)
    behavior: str
    behavior_probability: float = Field(default=1.0, gt=0, le=1)

    @model_validator(mode="after")
    def valid(self) -> Transition:
        if len(self.obs) != OBS_DIM or len(self.next_obs) != OBS_DIM:
            raise ValueError("resource observation shape mismatch")
        if any(not 0 <= v <= 1 for v in (*self.obs, *self.next_obs)):
            raise ValueError("normalized observation required")
        width = (OBS_DIM - 3) // 2
        if any(v not in (0.0, 1.0) for v in (*self.obs[width:], *self.next_obs[width:])):
            raise ValueError("known/mask channels must be binary")
        if any(len(m) != 3 or not m[0] for m in (self.mask, self.next_mask)):
            raise ValueError("invalid current/next mask")
        if (
            tuple(bool(v) for v in self.obs[-3:]) != self.mask
            or tuple(bool(v) for v in self.next_obs[-3:]) != self.next_mask
        ):
            raise ValueError("observation/mask disagree")
        if self.proposed != self.applied or not self.mask[self.applied]:
            raise ValueError("unavailable action or hidden action substitution")
        if not self.before_cutoff < self.action_seq < self.next_cutoff:
            raise ValueError("decision/event cutoff ordering violated")
        if (
            self.behavior
            not in ("noop", "static", "threshold", "resource_aware", "persistent_static")
            or self.behavior_probability != 1.0
        ):
            raise ValueError("only known deterministic fixture behavior is supported")
        if self.terminated:
            raise ValueError("this finite-horizon environment truncates, not naturally terminates")
        return self


def validate_episode(rows: tuple[Transition, ...]) -> None:
    if not rows or not rows[-1].truncated:
        raise ValueError("complete finite episode required")
    for i, row in enumerate(rows):
        if row.step != i or (row.truncated and i != len(rows) - 1):
            raise ValueError("overlap, missing step or early truncation")
        if (row.episode, row.seed, row.behavior, row.config_sha256, row.profile) != (
            rows[0].episode,
            rows[0].seed,
            rows[0].behavior,
            rows[0].config_sha256,
            rows[0].profile,
        ):
            raise ValueError("mixed episode identity")
        if i and (
            rows[i - 1].next_obs != row.obs
            or rows[i - 1].next_mask != row.mask
            or rows[i - 1].next_cutoff != row.before_cutoff
        ):
            raise ValueError("broken observation/mask/cutoff chain")


class PreparedReplay:
    """Bounded shape-check buffer. Unit fixtures cannot be admitted for training."""

    def __init__(self, capacity: int = 256) -> None:
        if type(capacity) is not int or not 1 <= capacity <= 4096:
            raise ValueError("bounded replay capacity required")
        self.rows: deque[Transition] = deque(maxlen=capacity)

    def append(self, row: Transition, *, for_training: bool = False) -> None:
        if for_training:
            raise PermissionError("unit instrumentation is ineligible for training")
        self.rows.append(row)

    def arrays(self) -> dict[str, NDArray[Any]]:
        if not self.rows:
            raise ValueError("empty replay")
        return {
            "obs": np.array([r.obs for r in self.rows], dtype=np.float32),
            "next_obs": np.array([r.next_obs for r in self.rows], dtype=np.float32),
            "masks": np.array([r.mask for r in self.rows], dtype=bool),
            "next_masks": np.array([r.next_mask for r in self.rows], dtype=bool),
            "actions": np.array([r.applied for r in self.rows], dtype=np.int64),
            "rewards": np.array([r.reward for r in self.rows], dtype=np.float32),
            "costs": np.array(
                [[getattr(r.costs, k) for k in COST_NAMES] for r in self.rows], dtype=np.float32
            ),
            # Return ends at the fixed horizon. Continuing-task learners need a new contract.
            "finite_terminal": np.array(
                [r.terminated or r.truncated for r in self.rows], dtype=bool
            ),
        }


def fixture_episode(env: ResourceEnv, policy: Policy, seed: int) -> tuple[Transition, ...]:
    """Evaluation-only microfixture, never a formal multi-policy study runner."""
    if env.config.horizon > 8 or type(seed) is not int or not 0 <= seed <= 9:
        raise ValueError("fixture limited to eight windows and fixture seeds0..9")
    config_sha = digest(env.config.model_dump_json().encode())
    obs, _ = env.reset(seed=seed)
    rows: list[Transition] = []
    for t in range(env.config.horizon):
        mask = env.action_masks()
        chosen = action(policy, obs)
        new, reward, terminated, truncated, info = env.step(chosen)
        rows.append(
            Transition(
                episode=f"unit:{env.family}:{seed}:{policy}:{env.fixed_static}:{config_sha[:12]}",
                config_sha256=config_sha,
                profile="persistent_static" if env.fixed_static else "budgeted",
                seed=seed,
                step=t,
                obs=tuple(float(v) for v in obs),
                mask=tuple(bool(v) for v in mask),
                proposed=chosen,
                applied=chosen,
                reward=reward,
                costs=Costs.model_validate(info["costs"]),
                next_obs=tuple(float(v) for v in new),
                next_mask=tuple(bool(v) for v in env.action_masks()),
                terminated=terminated,
                truncated=truncated,
                before_cutoff=info["before_cutoff_seq"],
                action_seq=info["action_seq"],
                next_cutoff=info["observation_cutoff_seq"],
                behavior="persistent_static" if env.fixed_static else policy,
            )
        )
        obs = new
    result = tuple(rows)
    validate_episode(result)
    return result


def settle_episode(env: ResourceEnv) -> tuple[Window, ...]:
    """Bounded evaluation-only drain, no arrivals/controls or additional decisions.

    Keep this separate from frozen policy transitions. A future training collector
    needs an approved terminal-cost contract; unit transitions remain ineligible.
    """
    if not env._ended or env.control is not None:
        raise ValueError("only a stopped episode may settle")
    windows: list[Window] = []
    bound = (env.config.deadline_ticks + env.config.window_ticks - 1) // env.config.window_ticks
    for _ in range(bound):
        if not env.service.pending:
            break
        windows.append(env.service.advance(()))
    if env.service.pending:
        raise AssertionError("deadline-bounded settlement failed")
    return tuple(windows)


def digest(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def write_unit_bundle(root: Path, output: Path) -> str:
    """One fixed unit receipt: mixed/seed0/four windows/threshold rule. No sweep.

    Refuses existing outputs. Source must be committed; failures remain on disk.
    This does not collect an approved research dataset or create any policy weights.
    """
    watched = [
        "rl-defense/rl_defense/research/resource",
        "docs/research/resource-exhaustion/PREREGISTRATION.md",
    ]
    if subprocess.check_output(
        ["git", "status", "--porcelain", "--", *watched], cwd=root, text=True
    ).strip():
        raise ValueError("commit the execution source/protocol first")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    source_files = {
        str(p.relative_to(root)): digest(p.read_bytes())
        for p in sorted((root / watched[0]).glob("*.py"))
    }
    for rel, sha in source_files.items():
        if digest(subprocess.check_output(["git", "show", f"{commit}:{rel}"], cwd=root)) != sha:
            raise ValueError("source does not belong to recorded Git commit")
    manifest = {
        "schema": "resource-unit-bundle/0.1",
        "purpose": "unit_instrumentation",
        "train_eligible": False,
        "training_authorized": False,
        "study_approved": False,
        "checkpoint": None,
        "gradients_applied": False,
        "source_commit": commit,
        "started_at": datetime.now(UTC).isoformat(),
        "source_files": source_files,
        "protocol_sha256": digest((root / watched[1]).read_bytes()),
        "seed": 0,
        "family": "mixed",
        "policy": "threshold",
        "environment": Config(horizon=4).model_dump(),
        "observation": OBS_VERSION,
        "actions": ACTION_VERSION,
        "python": sys.version,
        "platform": platform.platform(),
        "dependencies": {n: version(n) for n in ("numpy", "gymnasium", "pydantic")},
    }
    protocol_bytes = (root / watched[1]).read_bytes()
    if digest(
        subprocess.check_output(["git", "show", f"{commit}:{watched[1]}"], cwd=root)
    ) != digest(protocol_bytes):
        raise ValueError("protocol does not belong to recorded source")
    output.mkdir(parents=True, exist_ok=False)
    env = ResourceEnv(Config(horizon=4), family="mixed")
    try:
        rows = fixture_episode(env, "threshold", 0)
        if (
            any(digest((root / rel).read_bytes()) != sha for rel, sha in source_files.items())
            or (root / watched[1]).read_bytes() != protocol_bytes
        ):
            raise ValueError("execution source changed during unit capture")
        if (
            subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
            != commit
        ):
            raise ValueError("execution HEAD changed")
        (output / "trajectory.jsonl").write_text("".join(r.model_dump_json() + "\n" for r in rows))
        (output / "requests.json").write_text(
            json.dumps(
                {
                    "metrics_only_requests": [asdict(j) for j in env.service.jobs],
                    "events": env.service.events,
                    "control_ledger": env.ledger,
                    "attempts": env.attempts,
                },
                sort_keys=True,
                indent=2,
            )
            + "\n"
        )
        (output / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    except Exception as exc:
        (output / "FAILURE.json").write_text(
            json.dumps(
                {
                    "error": str(exc),
                    "manifest": manifest,
                    "metrics_only_requests": [asdict(j) for j in env.service.jobs],
                    "events": env.service.events,
                    "control_ledger": env.ledger,
                    "attempts": env.attempts,
                },
                sort_keys=True,
                indent=2,
            )
            + "\n"
        )
        raise
    files = {
        name: digest((output / name).read_bytes())
        for name in ("manifest.json", "trajectory.jsonl", "requests.json")
    }
    refs = [
        EvidenceRef(
            kind="artifact",
            artifact_id=f"art_{sha[:26]}",
            sha256=sha,
            provenance="resource-unit/0.1",
            note=name,
        ).model_dump(mode="json")
        for name, sha in files.items()
    ]
    index = (
        json.dumps(
            {"schema": "resource-unit-evidence/0.1", "files": files, "evidence": refs},
            sort_keys=True,
            indent=2,
        )
        + "\n"
    )
    (output / "EVIDENCE.json").write_text(index)
    return digest(index.encode())


def verify_unit_bundle(output: Path, *, expected_index_sha256: str) -> tuple[Transition, ...]:
    def read(name: str) -> bytes:
        with (output / name).open("rb") as stream:
            raw = stream.read(4 * 1024 * 1024 + 1)
        if len(raw) > 4 * 1024 * 1024:
            raise ValueError("unit evidence exceeds size limit")
        return raw

    raw = read("EVIDENCE.json")
    if digest(raw) != expected_index_sha256:
        raise ValueError("external evidence anchor mismatch")
    index = json.loads(raw)
    if index["schema"] != "resource-unit-evidence/0.1":
        raise ValueError("unsupported unit evidence schema")
    expected = {"manifest.json", "trajectory.jsonl", "requests.json"}
    if set(index["files"]) != expected:
        raise ValueError("unsupported evidence file set")
    blobs = {name: read(name) for name in expected}
    if any(digest(raw) != index["files"][name] for name, raw in blobs.items()):
        raise ValueError("unit evidence file changed")
    manifest = json.loads(blobs["manifest.json"])
    if (
        manifest["schema"] != "resource-unit-bundle/0.1"
        or manifest["observation"] != OBS_VERSION
        or manifest["actions"] != ACTION_VERSION
    ):
        raise ValueError("unsupported manifest/observation/action version")
    if manifest["gradients_applied"] is not False or manifest["study_approved"] is not False:
        raise ValueError("unit evidence cannot authorize a study or gradients")
    if (
        manifest["purpose"] != "unit_instrumentation"
        or manifest["train_eligible"] is not False
        or manifest["training_authorized"] is not False
        or manifest["checkpoint"] is not None
    ):
        raise ValueError("unit receipt cannot become training approval")
    rows = tuple(
        Transition.model_validate_json(line) for line in blobs["trajectory.jsonl"].splitlines()
    )
    validate_episode(rows)
    if len(rows) != manifest["environment"]["horizon"] or any(
        r.seed != manifest["seed"] for r in rows
    ):
        raise ValueError("manifest/episode identity mismatch")
    config = Config.model_validate(manifest["environment"])
    config_sha = digest(config.model_dump_json().encode())
    if any(
        r.config_sha256 != config_sha or r.profile != "budgeted" or r.behavior != manifest["policy"]
        for r in rows
    ):
        raise ValueError("configuration/profile/behavior provenance mismatch")
    requests = json.loads(blobs["requests.json"])
    jobs = requests["metrics_only_requests"]
    events = requests["events"]
    if [j["identifier"] for j in jobs] != list(range(len(jobs))):
        raise ValueError("request identity accounting mismatch")
    sequences = [e["available_seq"] for e in events]
    if sequences != sorted(set(sequences)) or (sequences and sequences[-1] >= rows[-1].next_cutoff):
        raise ValueError("event availability ordering mismatch")
    for j in jobs:
        if j["consumed"] + j["remaining"] != j["arrival"]["work"] or j["consumed"] < 0:
            raise ValueError("work conservation mismatch")
        if (
            sum(e["kind"] == "work" and e["job"] == j["identifier"] for e in events)
            != j["consumed"]
        ):
            raise ValueError("work ledger mismatch")
    for row in rows:
        current = [e for e in events if row.action_seq < e["available_seq"] < row.next_cutoff]
        adversarial_work = sum(
            e["kind"] == "work" and jobs[e["job"]]["arrival"]["adversarial"] for e in current
        )
        if row.reward != -adversarial_work:
            raise ValueError("reward/raw work mismatch")
        for name, kind in (
            ("legitimate_rate_denials", "rate_limited"),
            ("legitimate_capacity_denials", "capacity_rejected"),
            ("legitimate_timeouts", "timeout"),
        ):
            expected = sum(
                e["kind"] == kind and not jobs[e["job"]]["arrival"]["adversarial"] for e in current
            )
            if getattr(row.costs, name) != expected:
                raise ValueError("cost/raw outcome mismatch")
        expected_latency = sum(
            jobs[e["job"]]["finished"] - jobs[e["job"]]["arrival"]["tick"]
            for e in current
            if e["kind"] == "completed" and not jobs[e["job"]]["arrival"]["adversarial"]
        )
        if row.costs.legitimate_latency_sum != expected_latency:
            raise ValueError("latency/raw completion mismatch")
        activations = sum(
            x["event"] == "scheduled" and x["issued"] == row.step
            for x in requests["control_ledger"]
        )
        active = sum(
            x["event"] == "active" and x["window"] == row.step for x in requests["control_ledger"]
        )
        if (
            row.costs.applications != activations
            or row.costs.active_ticks != active * config.window_ticks
        ):
            raise ValueError("control ledger/cost mismatch")
        if row.costs.overhead_units != row.costs.applications * config.apply_overhead:
            raise ValueError("application overhead mismatch")
        work = sum(e["kind"] == "work" for e in current)
        if work + row.costs.overhead_units > config.workers * config.window_ticks:
            raise ValueError("worker budget exceeded")
    return rows
