"""Read immutable Git objects, without checkout, hooks, filters, imports or target execution."""

from __future__ import annotations

import hashlib
import os
import re
import selectors
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from pathspec import GitIgnoreSpec

from code_intelligence.models import IndexIssue, IntelligenceError, SourceFile
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


class GitReader:
    def __init__(
        self, local_path: Path, limits: Limits | None = None, include_prefix: str = ""
    ) -> None:
        self.path = local_path.resolve(strict=True)
        self.limits = limits or Limits()
        self.manifest: dict[str, str] = {}
        if include_prefix and (
            include_prefix.startswith("/")
            or "\\" in include_prefix
            or ".." in PurePosixPath(include_prefix).parts
        ):
            raise IntelligenceError("Index prefix must be a repository-relative directory")
        self.prefix = include_prefix.strip("/") + "/" if include_prefix else ""

    def run(self, *args: str, limit: int | None = None) -> bytes:
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
        with subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as proc:
            assert proc.stdout is not None and proc.stderr is not None
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
                issues.append(IndexIssue(path=path, reason=reason or "ignored at pinned SHA"))
                continue
            if pure.suffix not in {".py", ".md", ".rst", ".txt", ".toml", ".json", ".yaml", ".yml"}:
                issues.append(IndexIssue(path=path, reason="unsupported format"))
                continue
            total += size
            if total > self.limits.max_total_bytes:
                raise IntelligenceError("Repository exceeds max_total_bytes")
            raw = self.run("cat-file", "blob", oid, limit=self.limits.max_file_bytes)
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
