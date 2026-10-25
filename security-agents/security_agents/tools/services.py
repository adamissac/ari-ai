"""Execution services behind the sandbox-touching tools.

These own the dangerous operations (writing a worktree, running tests, running
a reviewed check template, applying a candidate diff to a fresh checkout) so
the tool handlers stay thin and every path check lives in one place.

`PatchWorktree` is also the shared repair-sandbox surface offered to Sai's
code-review repair loop (`code_review` consumes `PatchWorktree` + `TestRunner`
rather than duplicating shell execution). Interface published in the
coordination message to Sai.
"""

from __future__ import annotations

import ast
import configparser
import json
import os
import posixpath
import re
import shlex
import shutil
import stat
import tempfile
import tomllib
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..checks.library import CheckLibrary
from ..contracts import ErrorCode, PlatformError
from ..intel import CodeIntel
from ..sandbox.driver import SandboxDriver, SandboxLimits, SandboxProfile, SandboxResult, SandboxSpec
from ..sandbox.workspace import (
    changed_paths,
    copy_tree,
    diff_paths,
    fresh_checkout,
    recipe_test_roots,
    resolve_under,
    safe_rel_path,
    sha256_text,
    test_root_files,
    tree_digest,
    under_test_roots,
    unified_diff,
)
from .registry import ToolContext

PYTEST_SUMMARY = re.compile(
    r"(?:(?P<passed>\d+) passed)?(?:, )?(?:(?P<failed>\d+) failed)?(?:, )?(?:(?P<errors>\d+) error)?"
)
NODEID = re.compile(r"^(?P<file>[\w./-]+\.py)(?:::(?P<rest>[\w:\[\]-]+))?$")


def parse_pytest(stdout: str) -> dict[str, Any]:
    """Structured outcome from pytest output: counts plus failing test ids."""
    passed = failed = errors = skipped = 0
    for m in re.finditer(r"(\d+) (passed|failed|error|errors|skipped)", stdout):
        n, what = int(m.group(1)), m.group(2)
        if what == "passed":
            passed = n
        elif what == "failed":
            failed = n
        elif what.startswith("error"):
            errors = n
        elif what == "skipped":
            skipped = n
    failing = sorted(set(re.findall(r"^FAILED (\S+)", stdout, flags=re.MULTILINE))) or sorted(
        set(re.findall(r"^(\S+::\S+) FAILED", stdout, flags=re.MULTILINE))
    )
    listed = failing[:20]
    return {
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "skipped": skipped,
        "failing_tests": listed,
        "failing_truncated": failed > len(listed) or len(failing) > 20,
    }


def _supported_diff_path_prefixes(diff_text: str) -> bool:
    def supported(path: str) -> bool:
        return path == "/dev/null" or (path.startswith(("a/", "b/")) and len(path) > 2)

    in_hunk = False
    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            in_hunk = False
            if '"' in line:
                return False
            try:
                paths = shlex.split(line)[2:4]
            except ValueError:
                return False
            if len(paths) != 2 or not all(supported(path) for path in paths):
                return False
        elif line.startswith("@@ "):
            in_hunk = True
        elif line.startswith(("--- ", "+++ ")):
            if in_hunk:
                continue
            raw_path = line[4:].split("\t", 1)[0].strip()
            if raw_path.startswith('"'):
                return False
            try:
                paths = shlex.split(raw_path)
            except ValueError:
                return False
            if len(paths) != 1 or not supported(paths[0]):
                return False
        elif line.startswith(("rename from ", "rename to ", "copy from ", "copy to ")):
            if line.split(" ", 2)[2].lstrip().startswith('"'):
                return False
    return True


def _added_lines_by_diff_path(diff_text: str) -> dict[str, list[str]]:
    added: dict[str, list[str]] = {}
    current_path: str | None = None
    in_hunk = False
    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            in_hunk = False
            try:
                paths = shlex.split(line)[2:4]
            except ValueError:
                current_path = None
                continue
            target = next((path for path in paths if path.startswith("b/")), None)
            try:
                current_path = safe_rel_path(target[2:]) if target is not None else None
            except PlatformError:
                current_path = None
            continue
        if line.startswith("+++ ") and not in_hunk:
            raw_path = line[4:].split("\t", 1)[0].strip()
            if raw_path == "/dev/null":
                current_path = None
            elif raw_path.startswith("b/"):
                try:
                    current_path = safe_rel_path(raw_path[2:])
                except PlatformError:
                    current_path = None
            continue
        if line.startswith("@@ "):
            in_hunk = True
            continue
        if in_hunk and current_path is not None and line.startswith("+") and not line.startswith("+++ "):
            added.setdefault(current_path, []).append(line[1:])
    return added


def _pytest_sensitive_constructs(source: str) -> Counter[tuple[str, str, str]]:
    tree = ast.parse(source)
    constructs: Counter[tuple[str, str, str]] = Counter()

    def record(kind: str, name: str, node: ast.AST) -> None:
        segment = ast.get_source_segment(source, node) or ast.dump(node, include_attributes=False)
        constructs[(kind, name, segment)] += 1

    def assigned_names(targets: list[ast.expr]) -> set[str]:
        names: set[str] = set()

        def add_target(target: ast.expr) -> None:
            if isinstance(target, ast.Name):
                names.add(target.id)
            elif isinstance(target, (ast.Tuple, ast.List)):
                for element in target.elts:
                    add_target(element)
            elif isinstance(target, ast.Starred):
                add_target(target.value)

        for target in targets:
            add_target(target)
        return names

    def assigns_pytest_plugins(targets: list[ast.expr]) -> bool:
        return "pytest_plugins" in assigned_names(targets)

    def pytest_assignment_names(targets: list[ast.expr]) -> set[str]:
        return {name for name in assigned_names(targets) if name.startswith("pytest_")}

    def is_runner_module(name: str) -> bool:
        return any(name == prefix or name.startswith(f"{prefix}.") for prefix in ("_pytest", "pluggy"))

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("pytest_"):
            record("hook", node.name, node)

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for decorator in node.decorator_list:
                expression = decorator.func if isinstance(decorator, ast.Call) else decorator
                is_pytest_hookimpl = (
                    isinstance(expression, ast.Attribute)
                    and expression.attr == "hookimpl"
                    and isinstance(expression.value, ast.Name)
                    and expression.value.id == "pytest"
                )
                is_hookimpl = isinstance(expression, ast.Name) and expression.id == "hookimpl"
                if is_pytest_hookimpl or is_hookimpl:
                    name = ast.unparse(expression)
                    record("hookimpl", name, node)

        if isinstance(node, ast.Import):
            for alias in node.names:
                if is_runner_module(alias.name):
                    record("runner-import", alias.name, node)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if is_runner_module(module):
                record("runner-import", module, node)
        elif isinstance(node, ast.Call) and node.args:
            function = node.func
            is_importlib = (
                isinstance(function, ast.Attribute)
                and function.attr == "import_module"
                and isinstance(function.value, ast.Name)
                and function.value.id == "importlib"
            )
            is_builtin_import = isinstance(function, ast.Name) and function.id == "__import__"
            first_arg = node.args[0]
            if (
                (is_importlib or is_builtin_import)
                and isinstance(first_arg, ast.Constant)
                and isinstance(first_arg.value, str)
                and is_runner_module(first_arg.value)
            ):
                record("runner-import", first_arg.value, node)

        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign, ast.NamedExpr)):
            targets = [node.target]
        if targets and assigns_pytest_plugins(targets):
            record("pytest-plugins", "pytest_plugins", node)

    for node in tree.body:
        targets = (
            node.targets
            if isinstance(node, ast.Assign)
            else [node.target]
            if isinstance(node, ast.AnnAssign)
            else []
        )
        for name in sorted(pytest_assignment_names(targets)):
            record("pytest-assignment", name, node)

    return constructs


def _result_summary(res: SandboxResult) -> dict[str, Any]:
    return {
        "sandbox_run_id": res.run_id,
        "driver": res.driver,
        "isolation_level": res.isolation_level,
        "profile": res.profile,
        "network": res.network,
        "exit_code": res.exit_code,
        "timed_out": res.timed_out,
        "duration_s": round(res.duration_s, 3),
    }


TARGET_REQUEST = re.compile(r'"(GET|POST|PUT|PATCH|DELETE|HEAD) (\S+) HTTP/1\.[01]" (\d{3})')


def target_contact(target_log: str, transport: str) -> dict[str, Any]:
    requests = [
        {"method": m.group(1), "path": m.group(2), "status": int(m.group(3))}
        for m in TARGET_REQUEST.finditer(target_log or "")
    ]
    return {
        "transport": transport,
        "target_contacted": bool(requests),
        "target_requests": requests[:50],
        "target_log_sha256": sha256_text(target_log) if target_log else None,
    }


def workspace_path(workspace: Any) -> Path:
    """Resolve a provider's workspace to a directory path.

    Accepts a `Path` or a `PatchWorktree`. NOTE: `Path` itself has a `.root`
    attribute ("/"), so this must never duck-type on `.root` alone — doing so
    resolves a plain path to the filesystem root.
    """
    if isinstance(workspace, Path):
        return workspace
    root = getattr(workspace, "root", None)
    if isinstance(root, Path):
        return root
    if isinstance(workspace, str):
        return Path(workspace)
    raise PlatformError(
        ErrorCode.CONFLICT_STATE, f"cannot resolve a sandbox workspace from {type(workspace).__name__}"
    )


def _tail(text: str, lines: int = 40) -> str:
    rows = text.strip().splitlines()
    return "\n".join(rows[-lines:])


# --------------------------------------------------------------------------- worktree


@dataclass
class PatchWorktree:
    """Writable copy of the pinned snapshot. The only place Patch may write.

    `allowed_paths` comes from the approved RemediationPlan; new test files
    under the project's test roots are always permitted (the plan's test plan
    expects them). Everything else is rejected before touching disk.
    """

    snapshot_root: Path
    root: Path
    allowed_paths: frozenset[str]
    test_roots: tuple[str, ...] = ("tests/",)
    writes: list[str] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        intel: CodeIntel,
        dest: Path,
        allowed_paths: list[str],
        *,
        test_roots: tuple[str, ...] = ("tests/",),
    ) -> PatchWorktree:
        root = fresh_checkout(intel.snapshot, dest)
        return cls(
            snapshot_root=intel.snapshot.root,
            root=root,
            allowed_paths=frozenset(safe_rel_path(p) for p in allowed_paths),
            test_roots=test_roots,
        )

    def is_new_test_file(self, rel: str) -> bool:
        return any(rel.startswith(tr) for tr in self.test_roots) and not (self.snapshot_root / rel).is_file()

    def may_write(self, rel: str) -> bool:
        return rel in self.allowed_paths or self.is_new_test_file(rel)

    def write_file(self, path: str, content: str) -> dict[str, Any]:
        rel = safe_rel_path(path)
        if not self.may_write(rel):
            return {
                "error": "PATH_NOT_ALLOWED",
                "detail": (
                    f"{rel} is outside the approved remediation plan. Allowed: "
                    f"{sorted(self.allowed_paths)} plus new test files under {list(self.test_roots)}."
                ),
            }
        target = resolve_under(self.root, rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        existed = target.is_file()
        target.write_text(content, encoding="utf-8")
        self.writes.append(rel)
        return {
            "path": rel,
            "action": "updated" if existed else "created",
            "bytes": len(content.encode()),
            "lines": len(content.splitlines()),
        }

    def edit_file(self, path: str, old_string: str, new_string: str) -> dict[str, Any]:
        """Replace one exact, unique span of an existing file. Large files cannot be rewritten
        whole within the model's output limit; this sends only the change."""
        rel = safe_rel_path(path)
        if not self.may_write(rel):
            return self.write_file(path, "")  # same PATH_NOT_ALLOWED answer, nothing written
        target = resolve_under(self.root, rel)
        if not target.is_file():
            return {"error": "NOT_FOUND", "detail": f"{rel} does not exist; use worktree.write_file"}
        text = target.read_text(encoding="utf-8")
        count = text.count(old_string) if old_string else 0
        if count != 1:
            return {
                "error": "NO_UNIQUE_MATCH",
                "detail": f"old_string occurs {count} times in {rel}; include more surrounding lines",
            }
        target.write_text(text.replace(old_string, new_string, 1), encoding="utf-8")
        self.writes.append(rel)
        return {
            "path": rel,
            "action": "edited",
            "lines": len(target.read_text(encoding="utf-8").splitlines()),
        }

    def changed(self) -> list[str]:
        return changed_paths(self.snapshot_root, self.root)

    def diff_text(self) -> str:
        return unified_diff(self.snapshot_root, self.root, self.changed())

    def diff(self) -> dict[str, Any]:
        changed = self.changed()
        text = unified_diff(self.snapshot_root, self.root, changed)
        return {
            "files_changed": changed,
            "diff_sha256": sha256_text(text),
            "lines": len(text.splitlines()),
            "diff": text if len(text) <= 16_000 else text[:16_000] + "\n[truncated]",
        }


# --------------------------------------------------------------------------- test runner


@dataclass
class TestRunner:
    """Runs pytest in a `test-runner` sandbox (network none) over a workspace."""

    driver: SandboxDriver
    workspace_provider: Any  # callable(ctx) -> Path
    suite_workspace_provider: Any = None  # callable(ctx) -> Path for project_suite runs
    test_command_args: tuple[str, ...] = ("-q", "tests")
    limits: SandboxLimits = field(default_factory=SandboxLimits)
    setup: dict[str, tuple[str, ...]] = field(default_factory=dict)  # recipe `sandbox` block

    def run(self, ctx: ToolContext, selection: str, node_ids: list[str]) -> dict[str, Any]:
        if selection == "project_suite" and self.suite_workspace_provider is not None:
            if node_ids:
                return {
                    "error": "PROJECT_SUITE_NODE_IDS",
                    "detail": "Verify's project_suite runs the full pinned suite; node_ids are not allowed",
                }
            workspace = self.suite_workspace_provider(ctx)
            if workspace is None:
                return {
                    "error": "NO_VERIFY_WORKSPACE",
                    "detail": "patch.apply_fresh must succeed before project_suite",
                }
        else:
            workspace = self.workspace_provider(ctx)
        args: list[str] = ["-q"]
        if node_ids:
            for raw in node_ids:
                head = raw.split("::", 1)[0]
                safe_rel_path(head)  # reject traversal / absolute ids
                if not NODEID.match(raw):
                    return {"error": "BAD_NODE_ID", "detail": f"{raw!r} is not a valid pytest node id"}
                args.append(raw)
        elif selection in ("added_tests", "added_tests_unpatched"):
            roots = getattr(workspace, "test_roots", ("tests/",))
            added = [p for p in getattr(workspace, "writes", []) if under_test_roots(p, roots)]
            added = added or [p for p in ctx.artifacts.get("tests_added", []) if isinstance(p, str)]
            if not added:
                return {"error": "NO_ADDED_TESTS", "detail": "no new test files were written in this step"}
            args.extend(sorted(set(added)))
        else:
            args = list(self.test_command_args)
        ws_path = workspace_path(workspace)
        unpatched: Path | None = None
        if selection == "added_tests_unpatched":
            snapshot_root = getattr(workspace, "snapshot_root", None)
            if snapshot_root is None:
                return {
                    "error": "UNPATCHED_UNAVAILABLE",
                    "detail": "only a patch worktree has unpatched code",
                }
            # The pinned snapshot plus only the new test files: does the test catch the bug?
            unpatched = Path(tempfile.mkdtemp(prefix="unpatched-", dir=Path(ws_path).parent))
            copy_tree(Path(snapshot_root), unpatched / "ws")
            for rel in sorted({a.split("::", 1)[0] for a in args[1:]}):
                target = resolve_under(unpatched / "ws", rel)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(resolve_under(Path(ws_path), rel), target)
            ws_path = unpatched / "ws"
        spec = SandboxSpec(
            profile=SandboxProfile.TEST_RUNNER,
            network="none",
            workspace=ws_path,
            mode="pytest",
            args=args,
            labels={"assessment_id": ctx.assessment_id, "step_key": ctx.step_key, "agent": ctx.agent.value},
            limits=self.limits,
            **self.setup,
        )
        try:
            res = self.driver.run(spec)
        finally:
            if unpatched is not None:
                shutil.rmtree(unpatched, ignore_errors=True)
        summary = parse_pytest(res.stdout)
        ctx.audit.emit(
            "sandbox.tests_run",
            agent=ctx.agent.value,
            run_id=ctx.run_id,
            sandbox_run_id=res.run_id,
            selection=selection,
            **summary,
        )
        result = {
            **_result_summary(res),
            "selection": selection,
            "pytest_args": args,
            **summary,
            "stdout_tail": _tail(res.stdout),
            "stderr_tail": _tail(res.stderr, 15),
        }
        if self.suite_workspace_provider is not None:
            result["patch_id"] = ctx.artifacts.get("verify_patch_id")
        return result


# --------------------------------------------------------------------------- check runner


@dataclass
class CheckRunner:
    """Renders one reviewed template and runs it in a check-runner sandbox.

    The scope decision was already taken by the registry; it is re-validated
    here (defence in depth, and the driver requires it to attach a network).
    """

    driver: SandboxDriver
    library: CheckLibrary
    workspace_provider: Any  # callable(ctx) -> Path (the target workspace)
    recipe_provider: Any  # callable(ctx, target_id) -> dict
    limits: SandboxLimits = field(default_factory=lambda: SandboxLimits(timeout_s=180.0))
    transport: str = "inprocess"

    def run(
        self, ctx: ToolContext, template_ref: str, target_id: str, parameters: dict[str, Any]
    ) -> dict[str, Any]:
        decision = ctx.artifacts.get("last_scope_decision")
        if decision is None or not decision.allowed:
            raise PlatformError(ErrorCode.SCOPE_DENIED, "no allowed scope decision for this check run")
        meta = self.library.get(template_ref)
        if meta is None:
            return {
                "error": "UNKNOWN_TEMPLATE",
                "detail": f"{template_ref!r} is not in the library; call checks.list_templates first",
            }
        if not self.library.runnable(template_ref):
            return {
                "error": "TEMPLATE_NOT_RUNNABLE",
                "detail": f"{template_ref} has no reviewed implementation installed",
                "matches_expectation": None,
            }
        if self.transport == "http" and getattr(self.driver, "name", "") != "docker":
            return {
                "error": "HTTP_TRANSPORT_REQUIRES_DOCKER",
                "detail": "the http check transport needs the Docker driver's internal target network",
                "matches_expectation": None,
            }
        recipe = self.recipe_provider(ctx, target_id)
        try:
            rendered = self.library.render(template_ref, recipe, parameters, transport=self.transport)
        except PlatformError as exc:
            return {"error": exc.code.value, "detail": exc.message, "matches_expectation": None}

        try:
            setup = sandbox_setup(recipe)
        except PlatformError as exc:
            return {"error": exc.code.value, "detail": exc.message, "matches_expectation": None}
        check_file = "test_generated_check.py"
        spec = SandboxSpec(
            profile=SandboxProfile.CHECK_RUNNER,
            network="target-only",
            workspace=self.workspace_provider(ctx),
            mode="pytest",
            args=["-q", f".sandbox/{check_file}"],
            labels={
                "assessment_id": ctx.assessment_id,
                "step_key": ctx.step_key,
                "agent": ctx.agent.value,
                "template": meta.template_id,
            },
            limits=self.limits,
            extra_files={check_file: rendered},
            target_id=target_id,
            scope_decision=decision,
            target_workspace=workspace_path(self.workspace_provider(ctx))
            if self.transport == "http"
            else None,
            target_app=str(recipe.get("app_factory") or "") or None if self.transport == "http" else None,
            **setup,
        )
        res = self.driver.run(spec)
        summary = parse_pytest(res.stdout)
        # Deterministic verdict: the expectation holds only if every assertion passed.
        matches: bool | None
        if res.timed_out or res.exit_code is None or summary["errors"]:
            matches = None
        elif res.exit_code == 0 and summary["passed"] > 0:
            matches = True
        elif summary["failed"]:
            matches = False
        else:
            matches = None
        ctx.audit.emit(
            "sandbox.check_run",
            agent=ctx.agent.value,
            run_id=ctx.run_id,
            sandbox_run_id=res.run_id,
            template=template_ref,
            target_id=target_id,
            params_hash=self.library.params_hash(template_ref, parameters),
            scope_id=decision.scope_id,
            matches_expectation=matches,
            transport=self.transport,
        )
        return {
            **_result_summary(res),
            **target_contact(res.target_log, self.transport),
            "target_tree_sha256": tree_digest(spec.target_workspace) if spec.target_workspace else None,
            "template_ref": template_ref,
            "template_id": meta.template_id,
            "template_version": meta.version,
            "category": meta.category,
            "target_id": target_id,
            "parameters": parameters,
            "route": _route_of(recipe, parameters.get("route_id")),
            "params_hash": self.library.params_hash(template_ref, parameters),
            "matches_expectation": matches,
            **summary,
            "stdout_tail": _tail(res.stdout, 30),
            "note": (
                "matches_expectation is computed from the executed assertions; "
                "false means the expectation did not hold against the target."
            ),
        }


# --------------------------------------------------------------------------- patch applier


@dataclass
class PatchApplier:
    """Applies a candidate diff to a fresh checkout for Verify.

    Verify gets the diff artifact only: no Patch worktree, no Patch transcript.
    Also computes the deterministic scope/tampering facts Verify's verdict needs.
    """

    intel: CodeIntel
    artifacts: dict[str, Any]  # patch_id -> {"diff": str, "plan_files": [...], ...}
    workdir: Path

    def apply_fresh(self, ctx: ToolContext, patch_id: str) -> dict[str, Any]:
        record = self.artifacts.get(patch_id)
        if record is None:
            return {"error": "UNKNOWN_PATCH", "detail": f"no patch artifact {patch_id!r}"}
        diff_text = str(record["diff"])
        dest = self.workdir / f"verify-{patch_id}"
        if dest.exists():
            shutil.rmtree(dest)
        root = fresh_checkout(self.intel.snapshot, dest)
        ctx.artifacts["verify_patch_id"] = patch_id
        ctx.artifacts.pop("verify_suite_workspace", None)
        from ..sandbox.workspace import apply_diff

        if _supported_diff_path_prefixes(diff_text):
            ok, err = apply_diff(root, diff_text)
            touched = diff_paths(diff_text)
        else:
            ok, err = False, "unsupported diff path prefix"
            touched = []
        plan_files = [safe_rel_path(p) for p in record.get("plan_files", [])]
        roots = recipe_test_roots(self.intel.snapshot.root)
        new_tests = [p for p in touched if under_test_roots(p, roots) and not self.intel.snapshot.exists(p)]
        out_of_scope = [p for p in touched if p not in plan_files and p not in new_tests]
        protected_tests = record.get("protected_tests", [])
        tampered = set(self._tampered_tests(diff_text, protected_tests))
        plugin_residuals: list[str] = []
        if ok:
            try:
                tampered.update(self._tampered_test_contents(self.intel.snapshot.root, root, protected_tests))
                tampered.update(
                    self._tampered_runner_config(
                        diff_text,
                        self.intel.snapshot.root,
                        root,
                        residuals=plugin_residuals,
                    )
                )
            except PlatformError as exc:
                tampered.add(f"<{exc.message}> (protected-test discovery failed: {exc.code.value})")
            suite_dest = dest.parent / f"verify-suite-{patch_id}"
            try:
                ctx.artifacts["verify_suite_workspace"] = self._verify_suite_workspace(
                    self.intel.snapshot.root, root, suite_dest, roots
                )
            except (OSError, shutil.Error, PlatformError) as exc:
                ok = False
                err = f"verify suite workspace: {type(exc).__name__}"
                ctx.artifacts.pop("verify_suite_workspace", None)
        tampered_tests = sorted(tampered)
        ctx.artifacts["verify_workspace"] = root
        from ..regressions import RegressionEvidenceUnavailable, read_sources

        try:
            ctx.artifacts["regression_sources_before_tests"] = read_sources(
                root, list(record.get("tests_added") or [])
            )
        except (RegressionEvidenceUnavailable, PlatformError):
            ctx.artifacts["regression_sources_before_tests"] = None
        ctx.artifacts["verify_facts"] = {
            "applied": ok,
            "files_touched": touched,
            "out_of_scope": out_of_scope,
            "new_tests": new_tests,
            "tampered_protected_tests": tampered_tests,
            "diff_sha256": sha256_text(diff_text),
            "patch_id": patch_id,
            "plugin_discovery_residuals": plugin_residuals,
        }
        ctx.audit.emit(
            "patch.apply_fresh",
            agent=ctx.agent.value,
            run_id=ctx.run_id,
            patch_id=patch_id,
            applied=ok,
            out_of_scope=out_of_scope,
            tampered=tampered_tests,
        )
        return {
            "patch_id": patch_id,
            "applied": ok,
            "apply_error": err if not ok else "",
            "fresh_checkout": True,
            "diff_sha256": sha256_text(diff_text),
            "files_touched": touched,
            "files_in_plan": plan_files,
            "out_of_scope_files": out_of_scope,
            "new_test_files": new_tests,
            "tampered_protected_tests": tampered_tests,
        }

    @staticmethod
    def _verify_suite_workspace(
        snapshot_root: Path, patched_root: Path, destination: Path, test_roots: tuple[str, ...]
    ) -> Path:
        if os.path.lexists(destination):
            if destination.is_symlink() or not destination.is_dir():
                destination.unlink()
            else:
                shutil.rmtree(destination)
        copy_tree(patched_root, destination)

        for test_root in test_roots:
            rel_root = safe_rel_path(test_root)
            root = destination / rel_root
            if not os.path.lexists(root):
                continue
            if root.is_symlink():
                if not os.path.lexists(snapshot_root / rel_root):
                    root.unlink()
                continue
            if not root.is_dir():
                if not os.path.lexists(snapshot_root / rel_root):
                    root.unlink()
                continue
            for current, directories, files in os.walk(root, topdown=False, followlinks=False):
                current_path = Path(current)
                for name in files:
                    path = current_path / name
                    rel = path.relative_to(destination).as_posix()
                    if not os.path.lexists(snapshot_root / rel):
                        path.unlink()
                for name in directories:
                    path = current_path / name
                    rel = path.relative_to(destination).as_posix()
                    if os.path.lexists(snapshot_root / rel):
                        continue
                    if path.is_symlink():
                        path.unlink()
                    else:
                        path.rmdir()
        return destination

    @staticmethod
    def _tampered_tests(diff_text: str, protected: list[str]) -> list[str]:
        """Protected tests touched by changed hunks or file metadata in a diff."""
        discovery_failures = {path for path in protected if "protected-test discovery failed:" in path}
        protected_set = {safe_rel_path(p) for p in protected if p not in discovery_failures}
        tampered: set[str] = set()
        touched: set[str] = set()
        section_paths: set[str] = set()
        git_section = False
        new_file = False
        in_hunk = False
        old_remaining = 0
        new_remaining = 0

        def mark_unmapped_diff_path(raw: str | None = None) -> None:
            label = raw or "<diff header>"
            tampered.add(f"{label} (protected-test discovery failed: {ErrorCode.SNAPSHOT_NOT_READY.value})")

        def path_from_header(raw: str, *, strip_diff_prefix: bool = True) -> str | None:
            try:
                token = shlex.split(raw)[0]
            except (IndexError, PlatformError, ValueError):
                mark_unmapped_diff_path(raw)
                return None
            if token == "/dev/null":
                return None
            if strip_diff_prefix and token.startswith(("a/", "b/")):
                token = token[2:]
            try:
                return safe_rel_path(token)
            except PlatformError:
                mark_unmapped_diff_path(token)
                return None

        def mark_section() -> None:
            if not new_file:
                touched.update(section_paths & protected_set)

        for line in diff_text.splitlines():
            if line.startswith("diff --git "):
                mark_section()
                section_paths = set()
                git_section = True
                new_file = False
                in_hunk = False
                old_remaining = new_remaining = 0
                try:
                    header_paths = shlex.split(line)[2:4]
                except ValueError:
                    header_paths = []
                    mark_unmapped_diff_path(line)
                for token in header_paths:
                    if token.startswith(("a/", "b/")):
                        try:
                            section_paths.add(safe_rel_path(token[2:]))
                        except PlatformError:
                            mark_unmapped_diff_path(token)
                            continue
                    else:
                        mark_unmapped_diff_path(token)
                continue

            if in_hunk:
                if line.startswith(" "):
                    old_remaining -= 1
                    new_remaining -= 1
                elif line.startswith("\\"):
                    continue
                elif line.startswith("-"):
                    old_remaining -= 1
                    mark_section()
                elif line.startswith("+"):
                    new_remaining -= 1
                    mark_section()
                if line.startswith((" ", "+", "-")):
                    if old_remaining <= 0 and new_remaining <= 0:
                        in_hunk = False
                    continue
                else:
                    in_hunk = False

            if line.startswith("--- "):
                if not git_section:
                    mark_section()
                    section_paths = set()
                    new_file = False
                path = path_from_header(line[4:].split("\t", 1)[0].strip())
                if path is not None:
                    section_paths.add(path)
                continue
            if line.startswith("+++ "):
                path = path_from_header(line[4:].split("\t", 1)[0].strip())
                if path is not None:
                    section_paths.add(path)
                continue
            if line.startswith("new file mode "):
                new_file = True
                continue
            if line.startswith("deleted file mode "):
                mark_section()
                continue
            if line.startswith(("rename from ", "rename to ", "copy from ", "copy to ")):
                path = path_from_header(line.split(" ", 2)[2], strip_diff_prefix=False)
                if path is not None:
                    section_paths.add(path)
                mark_section()
                continue
            if line.startswith(("Binary files ", "GIT binary patch")):
                mark_section()
                continue
            if line.startswith("@@ "):
                hunk = re.match(r"^@@ -\d+(?:,(\d+))? \+\d+(?:,(\d+))? @@", line)
                if hunk is not None:
                    old_remaining = int(hunk.group(1) or 1)
                    new_remaining = int(hunk.group(2) or 1)
                    in_hunk = old_remaining > 0 or new_remaining > 0
                continue
        mark_section()
        return sorted(touched | tampered)

    @staticmethod
    def _tampered_runner_config(
        diff_text: str,
        snapshot_root: Path,
        patched_root: Path,
        *,
        residuals: list[str] | None = None,
    ) -> list[str]:
        """Test-runner configuration paths whose effective settings changed."""
        tampered: set[str] = set()

        def unreadable_config(path: str) -> None:
            tampered.add(f"{path} (pytest config unreadable: {ErrorCode.SNAPSHOT_NOT_READY.value})")

        def read_config(root: Path, path: str) -> bytes | None:
            candidate = root / path
            try:
                candidate.lstat()
            except FileNotFoundError:
                return None
            except OSError:
                unreadable_config(path)
                return None
            try:
                resolved = resolve_under(root, path)
                if not stat.S_ISREG(resolved.stat().st_mode):
                    raise OSError(f"configuration path is not a file: {path}")
                return resolved.read_bytes()
            except (OSError, PlatformError, RuntimeError, ValueError):
                unreadable_config(path)
                return None

        def ini_table(raw: bytes | None, section: str) -> tuple[bool, dict[str, str]]:
            config = configparser.ConfigParser(
                interpolation=None,
                default_section="__VERIFY_NO_DEFAULT_INHERITANCE__",
            )
            config.optionxform = str
            if raw is not None:
                config.read_string(raw.decode("utf-8"))
            present = config.has_section(section)
            items = dict(config.items(section, raw=True)) if present else {}
            return present, items

        def ini_option(raw: bytes | None, section: str, option: str) -> tuple[bool, bool, str | None]:
            present, items = ini_table(raw, section)
            return present, option in items, items.get(option)

        def nested_table(parsed: dict[str, Any], *keys: str) -> Any:
            current: Any = parsed
            for key in keys:
                if not isinstance(current, dict):
                    return None
                current = current.get(key)
            return current

        plugin_name_sources: dict[str, set[str]] = {}

        def add_plugin_name(names: set[str], raw: Any, source_path: str) -> None:
            if not isinstance(raw, str):
                return
            name = raw.strip()
            if not name.startswith("no:"):
                plugin = name.split(":", 1)[0]
                names.add(plugin)
                plugin_name_sources.setdefault(plugin, set()).add(source_path)

        def add_addopts(names: set[str], value: Any, source_path: str) -> None:
            values = value if isinstance(value, list) else [value]
            tokens: list[str] = []
            for item in values:
                if isinstance(item, str):
                    try:
                        tokens.extend(shlex.split(item))
                    except ValueError:
                        unreadable_config(source_path)
                elif item is not None:
                    unreadable_config(source_path)
            index = 0
            while index < len(tokens):
                token = tokens[index]
                if token == "-p":
                    if index + 1 < len(tokens):
                        add_plugin_name(names, tokens[index + 1], source_path)
                        index += 2
                        continue
                    unreadable_config(source_path)
                if token.startswith("-p") and token != "-p":
                    add_plugin_name(names, token[2:], source_path)
                index += 1

        plugin_names: set[str] = set()
        pythonpath_entries: dict[str, set[str]] = {"": set()}
        plugin_discovery_residuals: set[str] = set()
        pinned_config_paths: set[str] = set()
        ini_config_names = {"pytest.ini", ".pytest.ini", "tox.ini", "setup.cfg"}
        toml_config_names = {"pyproject.toml", "pytest.toml", ".pytest.toml"}
        ignored_config_dirs = {
            ".git",
            ".mypy_cache",
            ".pytest_cache",
            ".ruff_cache",
            ".venv",
            "__pycache__",
            "node_modules",
        }
        ini_config_paths: list[str] = []
        toml_config_paths: list[str] = []
        conftest_paths: list[str] = []

        def config_walk_error(error: OSError) -> None:
            raw_path = error.filename
            if raw_path:
                try:
                    failed_path = Path(raw_path).relative_to(snapshot_root).as_posix()
                except (OSError, ValueError):
                    failed_path = "build_recipe.json"
            else:
                failed_path = "build_recipe.json"
            unreadable_config(failed_path)

        for current, directories, files in os.walk(
            snapshot_root,
            followlinks=False,
            onerror=config_walk_error,
        ):
            current_path = Path(current)
            directories[:] = [
                name
                for name in directories
                if name not in ignored_config_dirs and not (current_path / name).is_symlink()
            ]
            for name in files:
                if name == "conftest.py":
                    conftest_paths.append((current_path / name).relative_to(snapshot_root).as_posix())
                if name not in ini_config_names | toml_config_names:
                    continue
                rel = (current_path / name).relative_to(snapshot_root).as_posix()
                if name in ini_config_names:
                    ini_config_paths.append(rel)
                else:
                    toml_config_paths.append(rel)

        def add_pythonpath(value: Any, source_path: str) -> None:
            values = value if isinstance(value, list) else [value]
            for item in values:
                if not isinstance(item, str):
                    if item is not None:
                        unreadable_config(source_path)
                    continue
                try:
                    for entry in shlex.split(item):
                        pythonpath_entries.setdefault(entry, set()).add(source_path)
                except ValueError:
                    unreadable_config(source_path)

        for path in ini_config_paths:
            name = path.rsplit("/", 1)[-1]
            section = "tool:pytest" if name == "setup.cfg" else "pytest"
            raw = read_config(snapshot_root, path)
            if raw is None:
                continue
            try:
                present, items = ini_table(raw, section)
            except (UnicodeDecodeError, configparser.Error):
                unreadable_config(path)
                continue
            if present:
                addopts = next((value for key, value in items.items() if key.casefold() == "addopts"), None)
                add_addopts(plugin_names, addopts, path)
                pythonpath = next(
                    (value for key, value in items.items() if key.casefold() == "pythonpath"),
                    None,
                )
                add_pythonpath(pythonpath, path)
            if name == "setup.cfg":
                try:
                    _, entry_points = ini_table(raw, "options.entry_points")
                    pytest11 = next(
                        (value for key, value in entry_points.items() if key.casefold() == "pytest11"),
                        None,
                    )
                    for line in (pytest11 or "").splitlines():
                        if "=" in line:
                            value = line.split("=", 1)[1].strip().split("#", 1)[0].strip()
                            if value:
                                add_plugin_name(plugin_names, value.split()[0], path)
                except (UnicodeDecodeError, configparser.Error):
                    unreadable_config(path)
                    continue

        for path in toml_config_paths:
            raw = read_config(snapshot_root, path)
            if raw is None:
                continue
            try:
                parsed = tomllib.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, tomllib.TOMLDecodeError):
                unreadable_config(path)
                continue
            ini_options = nested_table(parsed, "tool", "pytest", "ini_options")
            if isinstance(ini_options, dict):
                add_addopts(plugin_names, ini_options.get("addopts"), path)
                add_pythonpath(ini_options.get("pythonpath"), path)
            if path.rsplit("/", 1)[-1] in {"pytest.toml", ".pytest.toml"}:
                pytest_table = nested_table(parsed, "pytest")
                if isinstance(pytest_table, dict):
                    add_addopts(plugin_names, pytest_table.get("addopts"), path)
                    add_pythonpath(pytest_table.get("pythonpath"), path)
            for table in (
                nested_table(parsed, "project", "entry-points", "pytest11"),
                nested_table(parsed, "tool", "poetry", "plugins", "pytest11"),
            ):
                if isinstance(table, dict):
                    for value in table.values():
                        if not isinstance(value, str):
                            unreadable_config(path)
                            continue
                        add_plugin_name(plugin_names, value, path)

        unmappable_config_path = (
            f"build_recipe.json (unmappable pytest config path: {ErrorCode.SNAPSHOT_NOT_READY.value})"
        )

        def fail_closed_config_path() -> None:
            tampered.add(unmappable_config_path)

        recipe: dict[str, Any] = {}
        try:
            recipe_raw = read_config(snapshot_root, "build_recipe.json")
            parsed_recipe = json.loads((recipe_raw or b"{}").decode("utf-8"))
            if not isinstance(parsed_recipe, dict):
                raise ValueError("build_recipe.json must contain an object")
            recipe = parsed_recipe
        except (OSError, PlatformError, UnicodeDecodeError, ValueError, AttributeError):
            unreadable_config("build_recipe.json")
            fail_closed_config_path()
            recipe = {}

        if "test_roots" in recipe:
            raw_roots = recipe["test_roots"]
            if not isinstance(raw_roots, list) or not raw_roots:
                unreadable_config("build_recipe.json")
            else:
                try:
                    for raw_root in raw_roots:
                        if not isinstance(raw_root, str):
                            raise PlatformError(
                                ErrorCode.SNAPSHOT_NOT_READY,
                                "test_roots must contain relative paths",
                            )
                        safe_rel_path(raw_root)
                except PlatformError:
                    unreadable_config("build_recipe.json")
        if "protected_tests" in recipe:
            raw_protected_tests = recipe["protected_tests"]
            if not isinstance(raw_protected_tests, list):
                unreadable_config("build_recipe.json")
            else:
                try:
                    for raw_path in raw_protected_tests:
                        if not isinstance(raw_path, str):
                            raise PlatformError(
                                ErrorCode.SNAPSHOT_NOT_READY,
                                "protected_tests must contain relative paths",
                            )
                        safe_rel_path(raw_path)
                except PlatformError:
                    unreadable_config("build_recipe.json")

        command = recipe.get("test_command")
        if isinstance(command, str):
            try:
                command_tokens = shlex.split(command)
            except ValueError:
                command_tokens = []
                fail_closed_config_path()
        elif isinstance(command, list):
            if all(isinstance(item, str) for item in command):
                command_tokens = command
            else:
                command_tokens = []
                fail_closed_config_path()
        elif "test_command" not in recipe:
            command_tokens = []
        else:
            command_tokens = []
            fail_closed_config_path()
        add_addopts(plugin_names, command, "build_recipe.json")
        config_names = (
            "pytest.ini",
            ".pytest.ini",
            "pytest.toml",
            ".pytest.toml",
            "tox.ini",
            "setup.cfg",
            "pyproject.toml",
        )

        def config_changed_at(base_path: str, name: str) -> bool:
            path = f"{base_path}/{name}".strip("/")
            original_bytes = read_config(snapshot_root, path)
            patched_bytes = read_config(patched_root, path)
            if name in {"pytest.ini", ".pytest.ini", "pytest.toml", ".pytest.toml"}:
                return original_bytes != patched_bytes
            try:
                if name == "tox.ini":
                    return ini_table(original_bytes, "pytest") != ini_table(patched_bytes, "pytest")
                if name == "setup.cfg":
                    return ini_table(original_bytes, "tool:pytest") != ini_table(
                        patched_bytes, "tool:pytest"
                    ) or ini_option(original_bytes, "options.entry_points", "pytest11") != ini_option(
                        patched_bytes, "options.entry_points", "pytest11"
                    )
                original = tomllib.loads((original_bytes or b"").decode("utf-8"))
                patched = tomllib.loads((patched_bytes or b"").decode("utf-8"))
                fields = (
                    ("tool", "pytest"),
                    ("project", "entry-points", "pytest11"),
                    ("tool", "poetry", "plugins", "pytest11"),
                )
                return any(nested_table(original, *keys) != nested_table(patched, *keys) for keys in fields)
            except (UnicodeDecodeError, configparser.Error, tomllib.TOMLDecodeError):
                unreadable_config(path)
                return False

        def repo_relative_path(raw: str) -> str | None:
            candidate = Path(raw)
            try:
                if candidate.is_absolute():
                    raw = candidate.resolve().relative_to(snapshot_root.resolve()).as_posix()
                relative = safe_rel_path(posixpath.normpath(raw))
                resolve_under(snapshot_root, relative)
                return relative
            except (OSError, RuntimeError, ValueError, PlatformError):
                return None

        def normalize_config_path(
            raw: str,
            *,
            allow_root: bool = False,
            pin: bool = True,
        ) -> str | None:
            if not raw:
                fail_closed_config_path()
                return None
            normalized = raw
            while normalized.startswith("./"):
                normalized = normalized[2:]
            normalized = posixpath.normpath(normalized)
            if allow_root and normalized == ".":
                try:
                    snapshot_root.resolve()
                except (OSError, RuntimeError):
                    fail_closed_config_path()
                    return None
                return ""
            try:
                relative = safe_rel_path(normalized)
                resolved = resolve_under(snapshot_root, relative)
                resolved_relative = resolved.relative_to(snapshot_root.resolve()).as_posix()
            except (OSError, PlatformError, RuntimeError, ValueError):
                fail_closed_config_path()
                return None
            if pin:
                pinned_config_paths.update((relative, resolved_relative))
            return relative

        rootdirs: set[str] = set()
        index = 0
        while index < len(command_tokens):
            token = command_tokens[index]
            if token in {"-c", "--config-file", "--rootdir"}:
                if index + 1 >= len(command_tokens):
                    fail_closed_config_path()
                    index += 1
                    continue
                value = command_tokens[index + 1]
                index += 2
                if token == "--rootdir":
                    prefix = normalize_config_path(value, allow_root=True, pin=False)
                    if prefix is not None:
                        rootdirs.add(prefix)
                else:
                    normalize_config_path(value)
                continue
            if token.startswith("--config-file="):
                normalize_config_path(token.partition("=")[2])
            elif token.startswith("-c") and token != "-c":
                value = token[2:]
                normalize_config_path(value[1:] if value.startswith("=") else value)
            elif token.startswith("--rootdir="):
                prefix = normalize_config_path(token.partition("=")[2], allow_root=True, pin=False)
                if prefix is not None:
                    rootdirs.add(prefix)
            index += 1
        for rootdir in rootdirs:
            for name in ("pytest.ini", ".pytest.ini", "pytest.toml", ".pytest.toml"):
                normalize_config_path(f"{rootdir}/{name}".strip("/"))

        roots = recipe_test_roots(snapshot_root)
        plugin_source_paths = set(conftest_paths)
        try:
            plugin_source_paths.update(
                path for path in test_root_files(snapshot_root, roots) if path.endswith(".py")
            )
        except (OSError, PlatformError):
            for root in roots:
                unreadable_config(root.rstrip("/") or ".")
        for rel in sorted(plugin_source_paths):
            try:
                source = resolve_under(snapshot_root, rel).read_text(encoding="utf-8-sig")
                tree = ast.parse(source)
            except (OSError, PlatformError, UnicodeDecodeError, SyntaxError):
                unreadable_config(rel)
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    targets = node.targets
                    value = node.value
                elif isinstance(node, ast.AnnAssign):
                    targets = [node.target]
                    value = node.value
                elif isinstance(node, (ast.AugAssign, ast.NamedExpr)):
                    targets = [node.target]
                    value = None
                else:
                    continue
                if not any(
                    isinstance(child, ast.Name) and child.id == "pytest_plugins"
                    for target in targets
                    for child in ast.walk(target)
                ):
                    continue
                try:
                    literal = ast.literal_eval(value) if value is not None else None
                except (ValueError, TypeError, SyntaxError):
                    literal = None
                if isinstance(literal, str):
                    add_plugin_name(plugin_names, literal, rel)
                elif isinstance(literal, (list, tuple)) and all(isinstance(item, str) for item in literal):
                    for item in literal:
                        add_plugin_name(plugin_names, item, rel)
                else:
                    plugin_discovery_residuals.add(rel)

        pinned_plugin_paths: set[str] = set()
        pinned_plugin_directories: set[str] = set()
        try:
            snapshot_real = snapshot_root.resolve()
        except OSError:
            unreadable_config("build_recipe.json")
            snapshot_real = snapshot_root

        def protect_plugin_file(path: str, source_paths: set[str]) -> None:
            pinned_plugin_paths.add(path)
            try:
                resolved = resolve_under(snapshot_root, path)
                pinned_plugin_paths.add(resolved.relative_to(snapshot_real).as_posix())
            except (OSError, PlatformError, RuntimeError, ValueError):
                for source_path in source_paths:
                    unreadable_config(source_path)

        def protect_plugin_directory(path: str, source_paths: set[str]) -> None:
            pinned_plugin_directories.add(path)
            try:
                resolved = resolve_under(snapshot_root, path)
                pinned_plugin_directories.add(resolved.relative_to(snapshot_real).as_posix())
            except (OSError, PlatformError, RuntimeError, ValueError):
                for source_path in source_paths:
                    unreadable_config(source_path)

        for name in plugin_names:
            parts = name.split(".")
            if not parts or not all(part.isidentifier() for part in parts):
                for source_path in plugin_name_sources.get(name, set()):
                    unreadable_config(source_path)
                continue
            module_path = "/".join(parts)
            source_paths = plugin_name_sources.get(name, set())
            for entry, entry_sources in pythonpath_entries.items():
                try:
                    prefix = "" if entry in {"", ".", "./"} else repo_relative_path(entry)
                    if prefix is None:
                        for source_path in entry_sources:
                            unreadable_config(source_path)
                        continue
                    module_rel = f"{prefix}/{module_path}".strip("/")
                    protect_plugin_directory(module_rel, source_paths | entry_sources)
                    for suffix in (".py", ".pyi", ".so", ".pyd"):
                        protect_plugin_file(f"{module_rel}{suffix}", source_paths | entry_sources)
                    for parent_length in range(1, len(parts)):
                        parent = f"{prefix}/{'/'.join(parts[:parent_length])}".strip("/")
                        protect_plugin_file(f"{parent}/__init__.py", source_paths | entry_sources)
                        protect_plugin_file(f"{parent}.py", source_paths | entry_sources)

                    package_dir = resolve_under(snapshot_root, module_rel)
                    try:
                        package_stat = package_dir.stat()
                    except FileNotFoundError:
                        continue
                    if stat.S_ISDIR(package_stat.st_mode):
                        pinned_plugin_paths.update(test_root_files(snapshot_root, (f"{module_rel}/",)))
                except (OSError, PlatformError, RuntimeError, ValueError):
                    for source_path in source_paths | entry_sources:
                        unreadable_config(source_path)
                    continue
        if residuals is not None:
            residuals.extend(sorted(plugin_discovery_residuals))

        runner_shadowing_roots = {
            "pytest.py",
            "pytest",
            "_pytest",
            "pluggy",
            "pluggy.py",
            "py.py",
            "py",
            "sitecustomize.py",
            "usercustomize.py",
        }
        paths = diff_paths(diff_text)
        added_lines = _added_lines_by_diff_path(diff_text)
        roots = recipe_test_roots(snapshot_root)
        sensitive_addition = re.compile(
            r"^\s*(?:async\s+)?def\s+pytest_[A-Za-z_]\w*\s*\("
            r"|^\s*@\s*(?:pytest\s*\.\s*)?hookimpl\b"
            r"|^\s*(?:import|from)\s+(?:_pytest|pluggy)(?:\.|\s|$)"
            r"|^\s*pytest_plugins\s*(?::[^=]+)?(?:\+=|=)"
        )
        for path in paths:
            first_component = path.split("/", 1)[0]
            if (
                first_component in runner_shadowing_roots
                or ("/" not in path and path.endswith(".pth"))
                or path in pinned_plugin_paths
                or any(
                    path == directory or path.startswith(f"{directory}/")
                    for directory in pinned_plugin_directories
                )
            ):
                tampered.add(path)
                continue
            if path in pinned_config_paths:
                if read_config(snapshot_root, path) != read_config(patched_root, path):
                    tampered.add(path)
                continue
            name = path.rsplit("/", 1)[-1]
            if name == "conftest.py":
                tampered.add(path)
                continue
            if name in config_names:
                if config_changed_at(path.rpartition("/")[0], name):
                    tampered.add(path)
                continue
            if path.endswith(".py") and not under_test_roots(path, roots):
                try:
                    original_source = (
                        resolve_under(snapshot_root, path).read_text(encoding="utf-8-sig")
                        if os.path.lexists(snapshot_root / path)
                        else None
                    )
                    patched_source = (
                        resolve_under(patched_root, path).read_text(encoding="utf-8-sig")
                        if os.path.lexists(patched_root / path)
                        else None
                    )
                    original_constructs = (
                        _pytest_sensitive_constructs(original_source)
                        if original_source is not None
                        else Counter()
                    )
                    patched_constructs = (
                        _pytest_sensitive_constructs(patched_source)
                        if patched_source is not None
                        else Counter()
                    )
                except (OSError, PlatformError, UnicodeDecodeError, SyntaxError):
                    additions = added_lines.get(path, [])
                    has_sensitive_addition = any(sensitive_addition.search(line) for line in additions)
                    if has_sensitive_addition or additions or os.path.lexists(patched_root / path):
                        tampered.add(path)
                    continue
                if original_constructs != patched_constructs:
                    tampered.add(path)
                continue
        return sorted(tampered)

    @staticmethod
    def _tampered_test_contents(snapshot_root: Path, patched_root: Path, protected: list[str]) -> list[str]:
        """Protected tests whose pinned and successfully patched bytes differ."""
        tampered: set[str] = {path for path in protected if "protected-test discovery failed:" in path}
        for raw_path in protected:
            if "protected-test discovery failed:" in raw_path:
                continue
            path = safe_rel_path(raw_path)
            if not os.path.lexists(snapshot_root / path):
                try:
                    resolve_under(patched_root, path)
                    current = patched_root
                    for part in path.split("/"):
                        current = current / part
                        if current.is_symlink() and not os.path.exists(current):
                            tampered.add(path)
                            break
                except (OSError, PlatformError):
                    tampered.add(path)
                continue
            try:
                original = resolve_under(snapshot_root, path)
                if not original.is_file():
                    tampered.add(path)
                    continue
                original_bytes = original.read_bytes()
            except (OSError, PlatformError):
                tampered.add(path)
                continue
            try:
                patched = resolve_under(patched_root, path)
                if not patched.is_file():
                    tampered.add(path)
                    continue
                patched_bytes = patched.read_bytes()
            except (OSError, PlatformError):
                tampered.add(path)
                continue
            if original_bytes != patched_bytes:
                tampered.add(path)
        return sorted(tampered)


def _route_of(recipe: dict[str, Any], route_id: Any) -> dict[str, Any] | None:
    for route in recipe.get("routes", []):
        if isinstance(route, dict) and route.get("id") == route_id:
            return {
                "id": route_id,
                "method": str(route.get("method", "GET")).upper(),
                "path_template": route.get("path_template"),
            }
    return None


_PIP_REQ = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*(\[[A-Za-z0-9,._-]+\])?==[A-Za-z0-9.+!_-]+$")
_APT_PKG = re.compile(r"^[a-z0-9][a-z0-9+.-]{0,62}$")


def sandbox_setup(recipe: dict[str, Any]) -> dict[str, tuple[str, ...]]:
    """`pip`, `apt` and `include` from the recipe's optional `sandbox` block. The recipe is
    repository content, so only exact-pinned wheels, plain package names and safe relative
    paths pass; anything else is refused rather than dropped."""
    raw = recipe.get("sandbox") or {}
    if not isinstance(raw, dict):
        raise PlatformError(ErrorCode.SCHEMA_INVALID, "recipe sandbox must be an object")
    out: dict[str, tuple[str, ...]] = {}
    for key, check in (("pip", _PIP_REQ.match), ("apt", _APT_PKG.match), ("include", safe_rel_path)):
        items = raw.get(key) or []
        if not isinstance(items, list) or len(items) > 60 or not all(isinstance(i, str) for i in items):
            raise PlatformError(ErrorCode.SCHEMA_INVALID, f"recipe sandbox.{key} must be a list of strings")
        for item in items:
            if not check(item):
                raise PlatformError(
                    ErrorCode.SCHEMA_INVALID, f"recipe sandbox.{key} entry {item!r} is not allowed"
                )
        out[key] = tuple(safe_rel_path(i) for i in items) if key == "include" else tuple(items)
    return out


def recipe_from_snapshot(intel: CodeIntel) -> Any:
    """Recipe provider that reads the target's scope-approved build recipe."""

    def provider(ctx: ToolContext | None, target_id: str) -> dict[str, Any]:
        scope = getattr(ctx, "scope", None)
        if scope is not None and all(t.target_id != target_id for t in scope.targets):
            raise PlatformError(
                ErrorCode.SCOPE_DENIED, f"target {target_id[:80]!r} is not in the authorized scope"
            )
        path = intel.snapshot.root / "build_recipe.json"
        if not path.is_file():
            raise PlatformError(ErrorCode.SCHEMA_INVALID, "target has no build_recipe.json")
        return json.loads(path.read_text(encoding="utf-8"))

    return provider
