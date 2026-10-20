"""Versioned policy registry with human-approved promotion and rollback.

Deterministic gates, not prompts (docs/15):
- a version is the SHA-256 of a checkpoint plus the evaluation report produced for it;
- ``promote`` refuses unless the report's decision is ``recommend_promote``, the report
  was produced for exactly these checkpoint bytes and the current incumbent, and the
  operator supplies a user-shaped id (``usr_*``); this local CLI does not authenticate it;
- registered report bytes are hash-pinned; changed or legacy unpinned reports require
  explicit re-registration; this is integrity checking, not a report signature;
- ``rollback`` restores the previously deployed version; every change is appended to an
  audit history. Nothing here retrains or swaps a policy on its own.

    python -m rl_defense.live.registry status   [--registry runs/live/registry.json]
    python -m rl_defense.live.registry init     --checkpoint base.pt --approved-by usr_x
    python -m rl_defense.live.registry register --checkpoint cand.pt --report promotion_report.json
    python -m rl_defense.live.registry promote  --version <id> --approved-by usr_x --reason "..."
    python -m rl_defense.live.registry rollback --approved-by usr_x --reason "..."
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path

from rl_defense.checkpoint import sha256_file

DEFAULT_REGISTRY = Path(__file__).resolve().parents[2] / "runs" / "live" / "registry.json"
HUMAN_ID = re.compile(r"^usr_[A-Za-z0-9_]{1,64}$")


class RegistryError(Exception):
    pass


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _version_id(sha: str) -> str:
    return f"pol_{sha[:16]}"


class Registry:
    def __init__(self, path: Path = DEFAULT_REGISTRY) -> None:
        self.path = Path(path)
        if self.path.exists():
            self.data = json.loads(self.path.read_text())
        else:
            self.data = {"versions": {}, "deployed": None, "stack": [], "history": []}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2))

    # ---------------------------------------------------------------- queries
    @property
    def deployed(self) -> dict | None:
        vid = self.data["deployed"]
        return None if vid is None else self.data["versions"][vid]

    def deployed_checkpoint(self) -> Path:
        """Path of the deployed checkpoint, re-verified against its registered hash."""
        v = self.deployed
        if v is None:
            raise RegistryError("no policy is deployed")
        p = Path(v["checkpoint"])
        if sha256_file(p) != v["sha256"]:
            raise RegistryError(f"deployed checkpoint {p} no longer matches its registered hash")
        return p

    # ---------------------------------------------------------------- changes
    @staticmethod
    def _require_human(approved_by: str) -> None:
        if not HUMAN_ID.match(approved_by or ""):
            raise RegistryError(
                f"approval must come from a human user id (usr_*), got {approved_by!r}"
            )

    def register(self, checkpoint: Path, report: Path | None = None, note: str = "") -> str:
        checkpoint = Path(checkpoint).resolve()
        sha = sha256_file(checkpoint)
        vid = _version_id(sha)
        entry = {
            "id": vid,
            "checkpoint": str(checkpoint),
            "sha256": sha,
            "report": str(Path(report).resolve()) if report else None,
            "report_sha256": sha256_file(Path(report)) if report else None,
            "registered_at": _now(),
            "note": note,
        }
        existing = self.data["versions"].get(vid)
        if existing is None:
            self.data["versions"][vid] = entry
            self.data["history"].append({"action": "register", "version": vid, "at": _now()})
        elif report:
            # same bytes re-evaluated: the newest report is the one promotion checks
            existing["report"] = entry["report"]
            existing["report_sha256"] = entry["report_sha256"]
            self.data["history"].append(
                {"action": "attach_report", "version": vid, "report": entry["report"], "at": _now()}
            )
        return vid

    def init(self, checkpoint: Path, approved_by: str, reason: str = "initial deployment") -> str:
        """Deploy the first (baseline) policy. Allowed only when nothing is deployed."""
        self._require_human(approved_by)
        if self.data["deployed"] is not None:
            raise RegistryError("a policy is already deployed; use promote/rollback")
        vid = self.register(checkpoint, note="baseline")
        self.data["stack"] = [vid]
        self.data["deployed"] = vid
        self.data["history"].append(
            {"action": "init", "version": vid, "by": approved_by, "reason": reason, "at": _now()}
        )
        return vid

    def promote(self, version: str, approved_by: str, reason: str) -> None:
        self._require_human(approved_by)
        v = self.data["versions"].get(version)
        if v is None:
            raise RegistryError(f"unknown version {version}")
        if not v["report"]:
            raise RegistryError(f"{version} has no evaluation report; cannot promote")
        report_bytes = Path(v["report"]).read_bytes()
        if hashlib.sha256(report_bytes).hexdigest() != v.get("report_sha256"):
            raise RegistryError(f"{version}: report changed or is unpinned; register it again")
        report = json.loads(report_bytes)
        if report.get("decision") != "recommend_promote":
            raise RegistryError(
                f"{version}: report decision is {report.get('decision')!r}; failed checks: "
                + ", ".join(c["name"] for c in report.get("checks", []) if not c["passed"])
            )
        if report.get("candidate", {}).get("checkpoint_sha256") != v["sha256"]:
            raise RegistryError(f"{version}: report was produced for a different checkpoint")
        if sha256_file(Path(v["checkpoint"])) != v["sha256"]:
            raise RegistryError(f"{version}: checkpoint bytes changed since registration")
        # The local gate cannot deploy a layout the installed serving path refuses.
        from rl_defense.inference import PolicyRunner

        try:
            PolicyRunner(Path(v["checkpoint"]))
        except (ValueError, ImportError) as exc:
            raise RegistryError(f"{version}: checkpoint is not servable: {exc}") from exc
        if report.get("mode") == "online_dqfd":
            artifacts = report.get("artifacts", {})
            for name, expected in (
                ("checkpoint", v["sha256"]),
                (
                    "experience",
                    report.get("candidate", {}).get("lineage", {}).get("experience_sha256"),
                ),
            ):
                item = artifacts.get(name, {})
                path = Path(v["report"]).parent / item.get("path", "")
                if not expected or item.get("sha256") != expected or not path.is_file():
                    raise RegistryError(f"{version}: missing durable {name} evidence")
                if sha256_file(path) != expected:
                    raise RegistryError(f"{version}: {name} evidence hash mismatch")
        # A historical pass against a weaker baseline cannot replace the incumbent.
        incumbent = self.deployed
        if incumbent is None:
            raise RegistryError("no policy is deployed; use init for the baseline")
        self.deployed_checkpoint()  # refuse changed incumbent bytes, too
        if report.get("deployed", {}).get("checkpoint_sha256") != incumbent["sha256"]:
            raise RegistryError(f"{version}: report baseline differs from the deployed checkpoint")
        checks = report.get("checks")
        if (
            not isinstance(checks, list)
            or not checks
            or any(not isinstance(c, dict) or c.get("passed") is not True for c in checks)
        ):
            raise RegistryError(f"{version}: promotion requires nonempty passing checks")
        prev = self.data["deployed"]
        if version == prev:
            raise RegistryError(f"{version} is already deployed")
        self.data["stack"].append(version)
        self.data["deployed"] = version
        self.data["history"].append(
            {
                "action": "promote",
                "version": version,
                "previous": prev,
                "by": approved_by,
                "reason": reason,
                "at": _now(),
            }
        )

    def rollback(self, approved_by: str, reason: str) -> str:
        """Return to the version deployed before the current one (deployment stack)."""
        self._require_human(approved_by)
        stack = self.data["stack"]
        if len(stack) < 2:
            raise RegistryError("nothing to roll back to")
        cur = stack.pop()
        prev = stack[-1]
        self.data["deployed"] = prev
        self.data["history"].append(
            {
                "action": "rollback",
                "version": prev,
                "previous": cur,
                "by": approved_by,
                "reason": reason,
                "at": _now(),
            }
        )
        return prev


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("command", choices=["status", "init", "register", "promote", "rollback"])
    ap.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    ap.add_argument("--checkpoint")
    ap.add_argument("--report")
    ap.add_argument("--version")
    ap.add_argument("--approved-by", default="")
    ap.add_argument("--reason", default="")
    a = ap.parse_args(argv)
    reg = Registry(Path(a.registry))
    try:
        if a.command == "init":
            print(reg.init(Path(a.checkpoint), a.approved_by, a.reason or "initial deployment"))
        elif a.command == "register":
            print(reg.register(Path(a.checkpoint), Path(a.report) if a.report else None))
        elif a.command == "promote":
            reg.promote(a.version, a.approved_by, a.reason)
            print(f"deployed: {reg.data['deployed']}")
        elif a.command == "rollback":
            print(f"deployed: {reg.rollback(a.approved_by, a.reason)}")
        reg.save()
    except RegistryError as e:
        print(f"REFUSED: {e}")
        return 2
    print(
        json.dumps(
            {"deployed": reg.data["deployed"], "versions": list(reg.data["versions"])}, indent=2
        )
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
