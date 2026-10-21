"""Fingerprint all tracked repository files, including source/config edits without commits."""

import hashlib
import os
import subprocess
from pathlib import Path


def source_fingerprint(root: Path) -> str:
    repo = Path(
        subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    )
    names = subprocess.run(
        ["git", "ls-files", "-z"], cwd=repo, capture_output=True, check=True
    ).stdout.split(b"\0")
    digest = hashlib.sha256()
    for name in sorted(n for n in names if n):
        path = repo / os.fsdecode(name)
        digest.update(name + b"\0")
        if path.is_symlink():
            digest.update(b"symlink\0" + os.fsencode(os.readlink(path)))
        else:
            digest.update(b"file\0")
            with path.open("rb") as stream:
                while chunk := stream.read(1 << 20):
                    digest.update(chunk)
        digest.update(b"\0")
    return digest.hexdigest()
