"""Loading other owners' subsystems behind explicit factories.

A missing subsystem is reported as unavailable (never replaced by a fake): the
caller records ``SUBSYSTEM_UNAVAILABLE`` with the reason.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Loaded:
    obj: Any | None
    reason: str | None  # set when obj is None


def load_factory(spec: str, *args: Any, **kwargs: Any) -> Loaded:
    """``spec`` is ``module:callable``. Returns the callable's result, or why it is unavailable."""
    module_name, _, attr = spec.partition(":")
    if not module_name or not attr:
        return Loaded(None, f"invalid factory spec {spec!r}")
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        top = module_name.split(".")[0]
        if exc.name and (exc.name == module_name or exc.name.startswith(top)):
            return Loaded(None, f"{module_name} is not installed in this worker")
        raise
    factory = getattr(module, attr, None)
    if factory is None:
        return Loaded(None, f"{module_name} has no attribute {attr!r}")
    try:
        return Loaded(factory(*args, **kwargs), None)
    except Exception as exc:  # misconfigured subsystem: report it, never crash the job
        return Loaded(None, f"{spec} failed to initialize: {type(exc).__name__}: {exc}"[:400])
