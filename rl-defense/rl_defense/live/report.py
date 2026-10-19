"""The lab gateway as a runtime reporter: one window of records -> ``RuntimeSignalBatch``.

A reference implementation of what an operator's own gateway or sidecar sends to
``POST /api/v1/ingest/runtime/{project_id}`` (contracts 0.14). It sends aggregated
counters only (no payloads), per route template, with **pseudonymous** per-principal
counts: ``prn_`` plus an HMAC-SHA256 of the principal id under a key that only the reporter
holds, so the platform can name whom a block would cover without learning who it is. The
classification is the gateway's own: token principal versus object owner, with the
business's delegation grants applied (``cross_tenant_attempt``). The generator's
``is_attack`` label is never read.
"""

from __future__ import annotations

import hashlib
import hmac
import re
from collections.abc import Iterable
from datetime import datetime

from shared.monitoring import RuntimeSignalBatch, RuntimeSource

from rl_defense.live.gateway import RequestRecord

_TEMPLATES = (
    (re.compile(r"^/payments/[^/]+$"), "/payments/{payment_id}"),
    (re.compile(r"^/customers/[^/]+$"), "/customers/{customer_id}"),
)


def route_template(method: str, path: str) -> str:
    """payments-lite route template, so per-object paths aggregate into one route."""
    for rx, tmpl in _TEMPLATES:
        if rx.match(path):
            return f"{method.upper()} {tmpl}"
    return f"{method.upper()} {path}"


def pseudonym(principal: str, key: bytes) -> str:
    return "prn_" + hmac.new(key, principal.encode(), hashlib.sha256).hexdigest()[:24]


def route_windows(records: Iterable[RequestRecord], key: bytes) -> list[dict]:
    """``RouteWindow`` payloads (dicts) for one window of gateway records."""
    routes: dict[str, dict] = {}
    for r in records:
        rt = route_template(r.method, r.path)
        w = routes.setdefault(
            rt,
            {
                "route": rt,
                "requests": 0,
                "status_4xx": 0,
                "status_5xx": 0,
                "auth_failures": 0,
                "_p": {},
            },
        )
        w["requests"] += 1
        w["status_4xx"] += 400 <= r.status < 500
        w["status_5xx"] += r.status >= 500
        w["auth_failures"] += r.status in (401, 403)
        if r.principal is None:
            continue
        ref = pseudonym(r.principal, key)
        c = w["_p"].setdefault(ref, {"principal": ref, "cross_tenant": 0, "delegated": 0, "own": 0})
        if r.cross_tenant_attempt:
            c["cross_tenant"] += 1
        elif r.owner is not None and r.owner != r.principal:
            c["delegated"] += 1  # a foreign owner the detector did not flag: a grant covers it
        else:
            c["own"] += 1
    out = []
    for w in routes.values():
        w["principals"] = sorted(w.pop("_p").values(), key=lambda c: c["principal"])
        out.append(w)
    return sorted(out, key=lambda w: w["route"])


def runtime_batch(
    records: Iterable[RequestRecord],
    *,
    source: RuntimeSource,
    window_start: datetime,
    window_end: datetime,
    key: bytes,
) -> RuntimeSignalBatch:
    return RuntimeSignalBatch.model_validate(
        {
            "source": source,
            "window_start": window_start,
            "window_end": window_end,
            "routes": route_windows(records, key),
        }
    )


def main(argv: list[str] | None = None) -> int:
    """Write one lab window as a RuntimeSignalBatch JSON (test fixtures, demos)."""
    import argparse
    import json
    from datetime import UTC, timedelta

    from rl_defense.envs.defense_sim import NOOP_ACTION
    from rl_defense.live import evaluate as ev
    from rl_defense.live.adversary import live_app
    from rl_defense.live.loop import LiveDefenseLoop, LoopConfig
    from rl_defense.live.scenarios import load_scenarios

    ap = argparse.ArgumentParser(description=main.__doc__)
    ap.add_argument("--subdir", default="train_v3")
    ap.add_argument("--scenario", default="always_on_delegated")
    ap.add_argument("--seed", type=int, default=None, help="default: the scenario's first seed")
    ap.add_argument("--windows", type=int, default=1, help="noop windows to run; the last is sent")
    ap.add_argument("--key", default="fixture-reporter-key", help="reporter-only HMAC key")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    sc = next(s for s in load_scenarios("train", subdir=a.subdir) if s.name == a.scenario)
    loop = LiveDefenseLoop(
        live_app,
        config=LoopConfig(action_space="live_v3", **ev.V4_LOOP_OVERRIDES),
        driver=sc.driver(),
    )
    loop.reset(sc.seed_start if a.seed is None else a.seed)
    for _ in range(a.windows):
        loop.step(NOOP_ACTION)
    end = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)
    batch = runtime_batch(
        loop._gateway.records,
        source="simulated",
        window_start=end - timedelta(minutes=1),
        window_end=end,
        key=a.key.encode(),
    )
    attackers = sorted(pseudonym(p, a.key.encode()) for p in loop._flagged)
    loop.close()
    out = {
        "_generated_by": f"python -m rl_defense.live.report --subdir {a.subdir} "
        f"--scenario {a.scenario} --windows {a.windows} --out <path>",
        "_flagged_principals": attackers,
        "batch": batch.model_dump(mode="json"),
    }
    with open(a.out, "w") as fh:
        json.dump(out, fh, indent=2)
        fh.write("\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
