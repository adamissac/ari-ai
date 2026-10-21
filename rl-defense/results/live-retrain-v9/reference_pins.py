"""Fixed reference identities; guards do not rerun the completed experiment."""

from pathlib import Path

from rl_defense.checkpoint import sha256_file

PINS = {
    "v7": "d1c0c9b506fd29cc0e911aa6ad8d2a14943e7ece5ca03979a0377f043795108b",
    "v8": "ec8b5042fd56d2f75c6791b89152b57f4a6870c3656321b9f554056b4c0fc528",
}


def verify_files(root: Path) -> None:
    for name, expected in PINS.items():
        if sha256_file(root / f"results/live-retrain-{name}/candidate_online.pt") != expected:
            raise ValueError(f"fixed {name} reference checkpoint changed")


def verify_report(report: dict) -> None:
    actual = {r["name"]: r["checkpoint_sha256"] for r in report["references"]}
    if actual != PINS:
        raise ValueError("report does not evaluate the fixed v7/v8 references")
