"""Defense Lab simulation API: run one simulated episode on request.

``POST /lab/simulation/episodes`` computes a ``DefenseSimEnv`` episode for a chosen
scenario, policy and seed with ``rl_defense.lab_episode`` and returns every decision: the
observation, the valid actions, the network's Q-values, the action, the reward with its
components, and the simulator ground truth. ``GET /lab/simulation`` says whether the
engine and the pinned checkpoint are usable in this process, and why not when they are not.

Nothing here touches a real system, a project, or a live-defense control. The episode is
a simulation and is labelled as one. It is deterministic in its three inputs, so it holds
no server-side session: a refresh, a retry, or two users asking at once get the same bytes.
"""

from __future__ import annotations

import functools
import hashlib
import logging
import threading
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Request
from pydantic import Field

from backend.api.deps import ApiError, limiter, require_user
from backend.db import transaction
from shared.base import StrictModel
from shared.errors import ErrorCode

log = logging.getLogger("backend.api.lab")
router = APIRouter(tags=["defense-lab"])

REPO_ROOT = Path(__file__).resolve().parents[3]
LAB_CONFIG_DIR = REPO_ROOT / "rl-defense" / "configs"
LAB_CHECKPOINT = (
    REPO_ROOT / "rl-defense" / "results" / "protocol-v1-retrain" / "checkpoints" / "ddqn_seed0.pt"
)
# The integrity root for the lab policy. A checkpoint is a pickle; only these bytes load.
LAB_CHECKPOINT_SHA256 = "666145e00d4ee3b9a1839179d9d9aca5a245c20fe7a173e2cb960e34e0393fe8"
SIMULATION_LABEL = (
    "Simulated episode in DefenseSimEnv. Not telemetry from a real system; "
    "no action is executed anywhere."
)
EPISODES_PER_HOUR = 120
# One episode at a time per process: torch inference is CPU-bound and an episode is short.
_ENGINE_LOCK = threading.Lock()

LabPolicyKind = Literal["ddqn_trained", "ddqn_untrained", "random", "noop", "threshold_rules"]


class LabEpisodeRequest(StrictModel):
    scenario: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9_]+$")
    policy: LabPolicyKind
    episode_seed: int = Field(ge=0, le=2**31 - 1)


class LabUnavailable(Exception):
    """The simulation engine or its checkpoint cannot be used in this process."""


def _engine() -> Any:
    try:
        from rl_defense import lab_episode
    except ModuleNotFoundError as exc:
        raise LabUnavailable(
            f"the simulation engine is not installed in this API process ({exc.name})"
        ) from exc
    return lab_episode


def _checkpoint_digest() -> str:
    if not LAB_CHECKPOINT.is_file():
        raise LabUnavailable("the lab checkpoint is not present in this deployment")
    digest = hashlib.sha256(LAB_CHECKPOINT.read_bytes()).hexdigest()
    if digest != LAB_CHECKPOINT_SHA256:
        raise LabUnavailable("the lab checkpoint does not match its pinned sha256")
    return digest


def _scenarios(engine: Any) -> dict[str, Any]:
    found = engine.scenarios(LAB_CONFIG_DIR)
    if not found:
        raise LabUnavailable("no scenario configs are present in this deployment")
    return found


@functools.lru_cache(maxsize=64)
def _episode(scenario: str, policy: str, episode_seed: int) -> dict[str, Any]:
    """Deterministic in its arguments, so a repeat request is served from memory."""
    engine = _engine()
    config = _scenarios(engine).get(scenario)
    if config is None:
        raise KeyError(scenario)
    _checkpoint_digest()
    with _ENGINE_LOCK:
        episode = engine.run_lab_episode(
            config,
            policy,
            episode_seed,
            checkpoint=LAB_CHECKPOINT,
            expected_sha256=LAB_CHECKPOINT_SHA256,
        )
    return episode.model_dump(mode="json")


def _unavailable(reason: str) -> ApiError:
    return ApiError(ErrorCode.SUBSYSTEM_UNAVAILABLE, f"Lab simulation unavailable: {reason}", 503)


@router.get("/lab/simulation")
def lab_simulation_status(request: Request) -> dict[str, Any]:
    """What can be simulated here. ``available`` is false with a reason when it cannot."""
    with transaction() as conn:
        require_user(conn, request)
    status: dict[str, Any] = {
        "available": False,
        "unavailable_reason": None,
        "label": SIMULATION_LABEL,
        "scenarios": [],
        "policies": [],
        "checkpoint": None,
    }
    try:
        engine = _engine()
        configs = _scenarios(engine)
        digest = _checkpoint_digest()
    except LabUnavailable as exc:
        status["unavailable_reason"] = str(exc)
        return status
    status.update(
        available=True,
        env_id=engine.ENV_ID,
        scenarios=[
            {"name": c.name, "split": c.split, "horizon": c.horizon}
            for c in sorted(configs.values(), key=lambda c: (c.split != "eval", c.name))
        ],
        policies=list(engine.POLICY_KINDS),
        checkpoint={
            "sha256": digest,
            "policy_version": f"{engine.ENV_ID}@{digest[:12]}",
            "path": str(LAB_CHECKPOINT.relative_to(REPO_ROOT)),
        },
    )
    return status


@router.post("/lab/simulation/episodes")
def run_lab_simulation_episode(body: LabEpisodeRequest, request: Request) -> dict[str, Any]:
    with transaction() as conn:
        user = require_user(conn, request)
        limiter.check(f"lab_episode:{user.id}", EPISODES_PER_HOUR, 3600)
    try:
        episode = _episode(body.scenario, body.policy, body.episode_seed)
    except LabUnavailable as exc:
        raise _unavailable(str(exc)) from exc
    except KeyError as exc:
        raise ApiError(
            ErrorCode.VALIDATION_FAILED, f"unknown scenario: {body.scenario}", 422
        ) from exc
    except Exception as exc:  # a failed simulation is an error, never a partial success
        log.exception("lab episode failed")
        raise _unavailable(f"the episode failed ({type(exc).__name__})") from exc
    return {"label": SIMULATION_LABEL, "episode": episode}
