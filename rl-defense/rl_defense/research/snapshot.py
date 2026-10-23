"""Private, commit-owned source snapshots for public evidence certification."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory


def verification_commit(root: Path) -> str:
    """Capture the verifier revision before any provenance checks."""
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD^{commit}"], cwd=root, text=True
    ).strip()


@contextmanager
def source_snapshot(root: Path, commit: str):
    """Never execute later imports from the caller's mutable working checkout."""
    with TemporaryDirectory(prefix="rl-source-snapshot-") as private:
        checkout = Path(private) / "source"
        subprocess.run(
            [
                "git",
                "clone",
                "--quiet",
                "--no-checkout",
                "--no-local",
                "--no-hardlinks",
                str(root),
                str(checkout),
            ],
            check=True,
            capture_output=True,
            timeout=120,
        )
        subprocess.run(
            ["git", "checkout", "--quiet", "--detach", commit],
            cwd=checkout,
            check=True,
            capture_output=True,
            timeout=120,
        )
        if verification_commit(checkout) != commit:
            raise ValueError("verification snapshot revision changed")
        for directory, folders, files in os.walk(checkout):
            folders[:] = [d for d in folders if d != ".git"]
            for name in files:
                path = Path(directory) / name
                path.chmod(path.stat().st_mode & ~0o222)
            Path(directory).chmod(0o555)
        try:
            yield checkout
        finally:
            for directory, folders, files in os.walk(checkout):
                folders[:] = [d for d in folders if d != ".git"]
                Path(directory).chmod(0o755)
                for name in files:
                    path = Path(directory) / name
                    path.chmod(path.stat().st_mode | 0o200)


def certify_snapshot(
    root: Path, output: Path, index_blob: bytes, artifacts: dict[str, bytes], commit: str
) -> dict:
    from rl_defense.research.proof import read_artifact

    # This is a fixed allowlist, never paths taken from untrusted index metadata.
    extra = (
        "REVIEW_EVIDENCE.json",
        "REVIEW_RUNTIME.json",
        "REPORT_EVIDENCE.json",
        "README.md",
        "read_legacy.py",
        "legacy_readiness.json",
        "registry_guard.json",
        "transition.schema.json",
        "frozen/evaluate.py.txt",
        "frozen/source.commit.txt",
        "frozen/README.md",
    )
    captured = {"EVIDENCE.json": index_blob, **artifacts}
    for name in extra:
        path = output / name
        if path.exists():
            captured[name] = read_artifact(path)
    return _certify_source(root, captured, "study", commit)


def certify_legacy_snapshot(root: Path, captured: dict[str, bytes], commit: str) -> dict:
    return _certify_source(root, captured, "legacy", commit)


def _certify_source(root: Path, captured: dict[str, bytes], mode: str, commit: str) -> dict:
    with TemporaryDirectory(prefix="rl-evidence-snapshot-") as private:
        bundle = Path(private) / "evidence"
        bundle.mkdir(mode=0o700)
        for name, blob in captured.items():
            path = bundle / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(blob)
            path.chmod(0o400)
        with source_snapshot(root, commit) as checkout:
            if "source.commit.txt" in captured:
                subprocess.run(
                    ["git", "hash-object", "-t", "commit", "-w", "--stdin"],
                    input=captured["source.commit.txt"],
                    cwd=checkout,
                    check=True,
                    capture_output=True,
                )
            env = dict(os.environ)
            env["PYTHONPATH"] = os.pathsep.join(
                str(checkout / p)
                for p in (
                    "rl-defense",
                    "shared",
                    "standards",
                    "examples/payments-lite/target",
                )
            )
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            env["GIT_OPTIONAL_LOCKS"] = "0"
            command = "import json,sys; from pathlib import Path; from rl_defense.research.evaluate import _verify; print(json.dumps(_verify(Path(sys.argv[1]), sealed=True)))"
            if mode == "legacy":
                command = "import json,sys; from pathlib import Path; from rl_defense.research.legacy import _verify_legacy; print(json.dumps(_verify_legacy(Path(sys.argv[1]))))"
            elif mode != "study":
                raise ValueError("unknown source certification mode")
            result = subprocess.run(
                [sys.executable, "-c", command, str(bundle)],
                cwd=checkout,
                env=env,
                capture_output=True,
                text=True,
                timeout=300,
            )
            if result.returncode:
                raise ValueError(f"isolated certification failed: {result.stderr[-4000:]}")
            return json.loads(result.stdout)
