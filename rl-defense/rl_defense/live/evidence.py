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
    python -m rl_defense.live.evidence pack    results/live-retrain-v7 --run "..."

``pack`` builds the index for an evidence directory that ``online.run`` just wrote
(``promotion_report.json`` plus the uncompressed artifacts it names): the checkpoint is
stored as-is, the complete experience log gzip-compressed, and the selected snapshot's
experience as a line prefix of it (checked byte for byte). The uncompressed logs are then
removed; ``restore`` brings them back.

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


def _sha256(chunks: Iterator[bytes]) -> tuple[str, int]:
    h = hashlib.sha256()
    lines = 0
    for chunk in chunks:
        h.update(chunk)
        lines += chunk.count(b"\n")
    return h.hexdigest(), lines


def pack(evidence_dir: Path, run: str) -> dict:
    """Index (and compress) the artifacts ``promotion_report.json`` names."""
    d = Path(evidence_dir)
    arts = json.loads((d / "promotion_report.json").read_text())["artifacts"]
    ck, exp, sel = arts["checkpoint"], arts["experiment"], arts["experience"]
    ck_sha, _ = _sha256(_chunks_file(d / ck["path"]))
    exp_sha, exp_lines = _sha256(_chunks_file(d / exp["path"]))
    sel_sha, sel_lines = _sha256(_chunks_file(d / sel["path"]))
    for name, got, want in (
        ("checkpoint", ck_sha, ck["sha256"]),
        ("experiment", exp_sha, exp["sha256"]),
        ("selected_experience", sel_sha, sel["sha256"]),
    ):
        if got != want:
            raise ValueError(f"{name}: sha256 {got} != report {want}")
    prefix_sha, _ = _sha256(_chunks_prefix(_chunks_file(d / exp["path"]), sel_lines))
    if prefix_sha != sel_sha:
        raise ValueError("selected experience is not a line prefix of the experiment log")
    gz = d / (exp["path"] + ".gz")
    with (d / exp["path"]).open("rb") as src, gzip.GzipFile(gz, "wb", mtime=0) as dst:
        while chunk := src.read(_CHUNK):
            dst.write(chunk)
    idx = {
        "schema": SCHEMA,
        "run": run,
        "artifacts": {
            "checkpoint": {
                "path": ck["path"],
                "stored_as": "file",
                "sha256": ck_sha,
                "note": "the selected candidate; digest equals the report's checkpoint_sha256",
            },
            "experiment": {
                "path": exp["path"],
                "stored_as": "gzip",
                "stored_path": gz.name,
                "sha256": exp_sha,
                "note": f"complete log: demonstrations + all online transitions ({exp_lines} lines)",
            },
            "selected_experience": {
                "path": sel["path"],
                "stored_as": "prefix",
                "of": "experiment",
                "lines": sel_lines,
                "sha256": sel_sha,
                "note": "the data available at the selected snapshot; the hash the "
                "checkpoint's lineage.experience_sha256 pins",
            },
        },
    }
    (d / INDEX).write_text(json.dumps(idx, indent=2) + "\n")
    verify(d)  # the stored forms reproduce every pinned digest before anything is removed
    (d / exp["path"]).unlink()
    (d / sel["path"]).unlink()
    return idx


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("command", choices=["verify", "restore", "pack"])
    ap.add_argument("evidence_dir")
    ap.add_argument("--run", default="", help="pack: one line naming the run")
    args = ap.parse_args(argv)
    if args.command == "pack":
        for name, a in pack(Path(args.evidence_dir), args.run)["artifacts"].items():
            print(f"packed {name} {a['stored_as']} {a['sha256']}")
    elif args.command == "verify":
        for name, digest in verify(Path(args.evidence_dir)).items():
            print(f"ok {name} {digest}")
    else:
        for p in restore(Path(args.evidence_dir)):
            print(f"restored {p}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
