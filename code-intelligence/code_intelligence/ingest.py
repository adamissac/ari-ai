"""Read immutable Git objects, without checkout, hooks, filters, imports or target execution."""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import selectors
import subprocess
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath

from pathspec import GitIgnoreSpec

from code_intelligence.models import INDEX_VERSION, IndexIssue, IntelligenceError, SourceFile
from code_intelligence.privacy import redact

_SHA = re.compile(r"^[0-9a-f]{40}$")
_EXCLUDED = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "vendor",
    "vendors",
    "dist",
    "build",
    "__pycache__",
    ".next",
    "site-packages",
    ".mypy_cache",
    ".pytest_cache",
}
_SENSITIVE = {".npmrc", ".pypirc", ".netrc", "credentials.json", "id_rsa", "id_ed25519"}


@dataclass(frozen=True)
class Limits:
    max_files: int = 10_000
    max_file_bytes: int = 512_000
    max_total_bytes: int = 32_000_000
    max_tree_bytes: int = 8_000_000
    git_timeout_seconds: int = 30


def normalise_prefix(include_prefix: str) -> str:
    """Canonical directory coverage; validate even when an index is cached."""
    if not isinstance(include_prefix, str) or (
        include_prefix.startswith("/")
        or "\\" in include_prefix
        or ".." in PurePosixPath(include_prefix).parts
        or "\x00" in include_prefix
    ):
        raise IntelligenceError("Index prefix must be a repository-relative directory")
    prefix = str(PurePosixPath(include_prefix))
    return "" if prefix == "." else prefix


def ingestion_version(include_prefix: str, limits: Limits) -> str:
    """Opaque cache version includes every coverage and ingestion-budget setting."""
    prefix = normalise_prefix(include_prefix)
    if not prefix and limits == Limits():
        return INDEX_VERSION
    profile = json.dumps({"prefix": prefix, "limits": asdict(limits)}, sort_keys=True)
    digest = hashlib.sha256(profile.encode()).hexdigest()[:32]
    return f"{INDEX_VERSION}+profile.{digest}"


class GitReader:
    def __init__(
        self, local_path: Path, limits: Limits | None = None, include_prefix: str = ""
    ) -> None:
        self.path = local_path.resolve(strict=True)
        self.limits = limits or Limits()
        self.manifest: dict[str, str] = {}
        prefix = normalise_prefix(include_prefix)
        self.prefix = prefix + "/" if prefix else ""

    def run(self, *args: str, limit: int | None = None, stdin: bytes | None = None) -> bytes:
        # Never inherit Git tracing, object replacement, alternate worktrees or caller config.
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        env.update(
            {
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_CONFIG_GLOBAL": os.devnull,
                "GIT_NO_REPLACE_OBJECTS": "1",
                "GIT_NO_LAZY_FETCH": "1",
                "GIT_TERMINAL_PROMPT": "0",
            }
        )
        cmd = [
            "git",
            "--no-replace-objects",
            "--no-optional-locks",
            "-C",
            str(self.path),
            "-c",
            "core.fsmonitor=false",
            "-c",
            "core.pager=cat",
            *args,
        ]
        # Bound output while reading, including disk usage; never spool an entire huge tree.
        maximum = limit or self.limits.max_tree_bytes
        deadline = time.monotonic() + self.limits.git_timeout_seconds
        data = bytearray()
        with subprocess.Popen(
            cmd,
            env=env,
            stdin=subprocess.PIPE if stdin is not None else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ) as proc:
            assert proc.stdout is not None and proc.stderr is not None
            if stdin is not None:
                assert proc.stdin is not None
                feed = proc.stdin

                def write() -> None:  # a thread, so a full stdout pipe cannot deadlock us
                    with contextlib.suppress(BrokenPipeError):
                        feed.write(stdin)
                    feed.close()

                threading.Thread(target=write, daemon=True).start()
            try:
                with selectors.DefaultSelector() as selector:
                    selector.register(proc.stdout, selectors.EVENT_READ, True)
                    selector.register(proc.stderr, selectors.EVENT_READ, False)
                    while selector.get_map():
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            raise IntelligenceError("Git read timed out")
                        for event, _ in selector.select(remaining):
                            chunk = os.read(event.fd, 65_536)
                            if not chunk:
                                selector.unregister(event.fd)
                            elif event.data:
                                data.extend(chunk)
                                if len(data) > maximum:
                                    raise IntelligenceError("Git output exceeds configured limit")
                proc.wait(timeout=max(0.001, deadline - time.monotonic()))
            except subprocess.TimeoutExpired as exc:
                proc.kill()
                raise IntelligenceError("Git read timed out") from exc
            except BaseException:
                proc.kill()
                raise
            if proc.returncode:
                raise IntelligenceError(f"Git read failed: {args[0]}")
        return bytes(data)

    def read(self, sha: str) -> tuple[str, list[SourceFile], list[IndexIssue]]:
        if not _SHA.fullmatch(sha):
            raise IntelligenceError("Expected full lowercase 40-hex commit SHA")
        if self.run("cat-file", "-t", sha).strip() != b"commit":
            raise IntelligenceError("SHA must identify a commit")
        tree = self.run("rev-parse", f"{sha}^{{tree}}").decode().strip()
        entries: list[tuple[str, str, str, int]] = []
        ancestor_ignores: list[tuple[str, str, str, int]] = []
        issues: list[IndexIssue] = []
        for row in self.run("ls-tree", "-r", "-z", "-l", sha).split(b"\0"):
            if not row:
                continue
            info, raw_path = row.split(b"\t", 1)
            mode, kind, oid, size_text = info.decode().split()
            try:
                path = raw_path.decode("utf-8", errors="strict")
            except UnicodeDecodeError:
                issues.append(IndexIssue(path="<non-utf8>", reason="unsupported path encoding"))
                continue
            if (
                len(path) > 500
                or "\\" in path
                or any(ord(c) < 32 for c in path)
                or ".." in PurePosixPath(path).parts
            ):
                issues.append(IndexIssue(path="<unsupported>", reason="unsafe or long path"))
                continue
            if self.prefix and not path.startswith(self.prefix):
                pure = PurePosixPath(path)
                parent = str(pure.parent)
                if (
                    pure.name in {".gitignore", ".intelignore"}
                    and kind == "blob"
                    and mode in {"100644", "100755"}
                    and (parent == "." or self.prefix.startswith(parent + "/"))
                ):
                    ancestor_ignores.append((path, oid, mode, int(size_text)))
                continue
            self.manifest[path] = oid
            if kind != "blob" or mode not in {"100644", "100755"}:
                issues.append(IndexIssue(path=path, reason="symlink or submodule excluded"))
                continue
            entries.append((path, oid, mode, int(size_text)))
        if len(entries) > self.limits.max_files:
            raise IntelligenceError("Repository exceeds max_files")

        rules: list[tuple[str, GitIgnoreSpec]] = []
        for path, oid, _, size in [*ancestor_ignores, *entries]:
            if PurePosixPath(path).name in {".gitignore", ".intelignore"}:
                if size > self.limits.max_file_bytes:
                    raise IntelligenceError("Ignore file exceeds max_file_bytes")
                ignore_content = self.run("cat-file", "blob", oid, limit=self.limits.max_file_bytes)
                parent = str(PurePosixPath(path).parent)
                rules.append(
                    (
                        "" if parent == "." else parent + "/",
                        GitIgnoreSpec.from_lines(ignore_content.decode("utf-8").splitlines()),
                    )
                )
        rules.sort(key=lambda x: (len(x[0]), x[0]))
        files: list[SourceFile] = []
        total = 0
        # Decisions in tree order (an issue, or a blob to read), so issues keep their order.
        plan: list[IndexIssue | tuple[str, str, PurePosixPath]] = []
        for path, oid, _, size in entries:
            pure = PurePosixPath(path)
            reason = None
            if any(p in _EXCLUDED for p in pure.parts):
                reason = "vendored or generated directory"
            elif (
                pure.name.startswith(".env")
                or pure.name in _SENSITIVE
                or pure.suffix
                in {
                    ".key",
                    ".pem",
                    ".p12",
                    ".pfx",
                    ".lock",
                    ".min.js",
                    ".map",
                }
            ):
                reason = "sensitive or generated file"
            elif size > self.limits.max_file_bytes:
                reason = "oversized file"
            ignored = False
            for prefix, spec in rules:
                if not path.startswith(prefix):
                    continue
                # A negated child cannot re-include an excluded parent directory.
                relative = path[len(prefix) :]
                parts = relative.split("/")
                if any(spec.match_file("/".join(parts[:i]) + "/") for i in range(1, len(parts))):
                    ignored = True
                    break
                result = spec.check_file(relative)
                if result.include is not None:
                    ignored = result.include
            if reason or ignored:
                plan.append(IndexIssue(path=path, reason=reason or "ignored at pinned SHA"))
                continue
            if pure.suffix not in {".py", ".md", ".rst", ".txt", ".toml", ".json", ".yaml", ".yml"}:
                plan.append(IndexIssue(path=path, reason="unsupported format"))
                continue
            total += size
            if total > self.limits.max_total_bytes:
                raise IntelligenceError("Repository exceeds max_total_bytes")
            plan.append((path, oid, pure))
        # One `git cat-file --batch` for every selected blob instead of a process per file.
        blobs = self._blobs([item[1] for item in plan if not isinstance(item, IndexIssue)], total)
        for item in plan:
            if isinstance(item, IndexIssue):
                issues.append(item)
                continue
            path, oid, pure = item
            raw = blobs[oid]
            try:
                content = raw.decode("utf-8")
            except UnicodeDecodeError:
                issues.append(IndexIssue(path=path, reason="binary or non-UTF8"))
                continue
            if "\0" in content or any(
                marker in content[:1000].lower()
                for marker in (
                    "@generated",
                    "auto-generated",
                    "automatically generated",
                    "do not edit",
                )
            ):
                issues.append(IndexIssue(path=path, reason="binary or generated content"))
                continue
            content = redact(content)
            files.append(
                SourceFile(
                    path=path,
                    blob_sha=oid,
                    content_sha256=hashlib.sha256(content.encode()).hexdigest(),
                    language="python" if pure.suffix == ".py" else "text",
                    is_test=pure.name.startswith("test_")
                    or pure.name.endswith("_test.py")
                    or "tests" in pure.parts,
                    content=content,
                )
            )
        return tree, files, issues

    def _blobs(self, oids: list[str], total: int) -> dict[str, bytes]:
        if not oids:
            return {}
        out = self.run(
            "cat-file",
            "--batch",
            stdin="".join(f"{oid}\n" for oid in oids).encode(),
            limit=total + 128 * len(oids),
        )
        blobs: dict[str, bytes] = {}
        pos = 0
        for oid in oids:
            end = out.index(b"\n", pos)
            header = out[pos:end].split()
            if len(header) != 3 or header[0].decode() != oid or header[1] != b"blob":
                raise IntelligenceError("Git blob read failed")
            size = int(header[2])
            blobs[oid] = out[end + 1 : end + 1 + size]
            pos = end + 1 + size + 1  # content, then a newline
        return blobs
