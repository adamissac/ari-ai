"""Restore and verify hash-pinned evidence that is stored compressed in the repo.

Large experience logs compress about 39× (repetitive JSON), so an evidence directory can
commit ``<file>.gz`` instead of ``<file>``. ``EVIDENCE.json`` in that directory lists
every artifact: its SHA-256 over the **uncompressed** bytes, where its bytes come from
(stored as-is, gzip-compressed, or derived as a line prefix of another artifact), and
why. ``restore`` writes the uncompressed files next to it, so the registry's checks
(``registry.promote``) read the exact pinned bytes. ``verify`` re-hashes every artifact by
streaming, without writing anything.

    python -m rl_defense.live.evidence verify  results/live-retrain-v6
    python -m rl_defense.live.evidence restore results/live-retrain-v6

Nothing here trusts a filename: every byte stream is checked against the pinned digest,
and a mismatch is an error.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from collections.abc import Iterator
from pathlib import Path

INDEX = "EVIDENCE.json"
SCHEMA = "live-evidence-index/0.1"
_CHUNK = 1 << 20


def _chunks_file(path: Path) -> Iterator[bytes]:
    with path.open("rb") as fh:
        while chunk := fh.read(_CHUNK):
            yield chunk


def _chunks_gzip(path: Path) -> Iterator[bytes]:
    with gzip.open(path, "rb") as fh:
        while chunk := fh.read(_CHUNK):
            yield chunk


def _chunks_prefix(source: Iterator[bytes], lines: int) -> Iterator[bytes]:
    """The first ``lines`` newline-terminated lines of a byte stream."""
    left = lines
    buf = b""
    for chunk in source:
        buf += chunk
        while left and (i := buf.find(b"\n")) >= 0:
            yield buf[: i + 1]
            buf = buf[i + 1 :]
            left -= 1
        if not left:
            return
    if left:
        raise ValueError(f"source ended {left} lines before the requested prefix")


def load_index(evidence_dir: Path) -> dict:
    idx = json.loads((Path(evidence_dir) / INDEX).read_text())
    if idx.get("schema") != SCHEMA:
        raise ValueError(f"{INDEX}: unknown schema {idx.get('schema')!r}")
    return idx


def stream(evidence_dir: Path, name: str, idx: dict | None = None) -> Iterator[bytes]:
    """The uncompressed bytes of artifact ``name``, from wherever they are stored."""
    d = Path(evidence_dir)
    idx = idx or load_index(d)
    a = idx["artifacts"][name]
    kind = a["stored_as"]
    if kind == "file":
        return _chunks_file(d / a["path"])
    if kind == "gzip":
        return _chunks_gzip(d / a["stored_path"])
    if kind == "prefix":
        return _chunks_prefix(stream(d, a["of"], idx), int(a["lines"]))
    raise ValueError(f"{name}: unknown storage {kind!r}")


def verify(evidence_dir: Path) -> dict[str, str]:
    """Re-hash every artifact; raise on the first mismatch. Returns name -> sha256."""
    d = Path(evidence_dir)
    idx = load_index(d)
    out: dict[str, str] = {}
    for name, a in idx["artifacts"].items():
        h = hashlib.sha256()
        for chunk in stream(d, name, idx):
            h.update(chunk)
        if h.hexdigest() != a["sha256"]:
            raise ValueError(f"{name}: sha256 {h.hexdigest()} != pinned {a['sha256']}")
        out[name] = h.hexdigest()
    return out


def restore(evidence_dir: Path) -> list[Path]:
    """Write every non-file artifact's uncompressed bytes to its ``path`` (verified)."""
    d = Path(evidence_dir)
    idx = load_index(d)
    written: list[Path] = []
    for name, a in idx["artifacts"].items():
        if a["stored_as"] == "file":
            continue
        target = d / a["path"]
        tmp = target.with_name(target.name + ".partial")
        h = hashlib.sha256()
        with tmp.open("wb") as fh:
            for chunk in stream(d, name, idx):
                h.update(chunk)
                fh.write(chunk)
        if h.hexdigest() != a["sha256"]:
            tmp.unlink()
            raise ValueError(f"{name}: sha256 {h.hexdigest()} != pinned {a['sha256']}")
        tmp.replace(target)
        written.append(target)
    return written


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("command", choices=["verify", "restore"])
    ap.add_argument("evidence_dir")
    args = ap.parse_args(argv)
    if args.command == "verify":
        for name, digest in verify(Path(args.evidence_dir)).items():
            print(f"ok {name} {digest}")
    else:
        for p in restore(Path(args.evidence_dir)):
            print(f"restored {p}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
