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

import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..checks.library import CheckLibrary
from ..contracts import ErrorCode, PlatformError
from ..intel import CodeIntel
from ..sandbox.driver import SandboxDriver, SandboxLimits, SandboxProfile, SandboxResult, SandboxSpec
from ..sandbox.workspace import (
    changed_paths,
    diff_paths,
    fresh_checkout,
    resolve_under,
    safe_rel_path,
    sha256_text,
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

    def changed(self) -> list[str]:
        return changed_paths(self.snapshot_root, self.root)

    def diff_text(self) -> str:
        return unified_diff(self.snapshot_root, self.root, self.changed())

    def diff(self) -> dict[str, Any]:
        changed = self.changed()
        text = self.diff_text()
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
    test_command_args: tuple[str, ...] = ("-q", "tests")
    limits: SandboxLimits = field(default_factory=SandboxLimits)

    def run(self, ctx: ToolContext, selection: str, node_ids: list[str]) -> dict[str, Any]:
        workspace = self.workspace_provider(ctx)
        args: list[str] = ["-q"]
        if node_ids:
            for raw in node_ids:
                head = raw.split("::", 1)[0]
                safe_rel_path(head)  # reject traversal / absolute ids
                if not NODEID.match(raw):
                    return {"error": "BAD_NODE_ID", "detail": f"{raw!r} is not a valid pytest node id"}
                args.append(raw)
        elif selection == "added_tests":
            added = [p for p in getattr(workspace, "writes", []) if p.startswith("tests/")]
            added = added or [p for p in ctx.artifacts.get("tests_added", []) if isinstance(p, str)]
            if not added:
                return {"error": "NO_ADDED_TESTS", "detail": "no new test files were written in this step"}
            args.extend(sorted(set(added)))
        else:
            args = list(self.test_command_args)
        ws_path = workspace_path(workspace)
        spec = SandboxSpec(
            profile=SandboxProfile.TEST_RUNNER,
            network="none",
            workspace=ws_path,
            mode="pytest",
            args=args,
            labels={"assessment_id": ctx.assessment_id, "step_key": ctx.step_key, "agent": ctx.agent.value},
            limits=self.limits,
        )
        res = self.driver.run(spec)
        summary = parse_pytest(res.stdout)
        ctx.audit.emit(
            "sandbox.tests_run",
            agent=ctx.agent.value,
            run_id=ctx.run_id,
            sandbox_run_id=res.run_id,
            selection=selection,
            **summary,
        )
        return {
            **_result_summary(res),
            "selection": selection,
            "pytest_args": args,
            **summary,
            "stdout_tail": _tail(res.stdout),
            "stderr_tail": _tail(res.stderr, 15),
        }


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
            "template_ref": template_ref,
            "template_id": meta.template_id,
            "template_version": meta.version,
            "category": meta.category,
            "target_id": target_id,
            "parameters": parameters,
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
        from ..sandbox.workspace import apply_diff

        ok, err = apply_diff(root, diff_text)
        touched = diff_paths(diff_text)
        plan_files = [safe_rel_path(p) for p in record.get("plan_files", [])]
        new_tests = [p for p in touched if p.startswith("tests/") and not self.intel.snapshot.exists(p)]
        out_of_scope = [p for p in touched if p not in plan_files and p not in new_tests]
        tampered = self._tampered_tests(diff_text, record.get("protected_tests", []))
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
            "tampered_protected_tests": tampered,
            "diff_sha256": sha256_text(diff_text),
        }
        ctx.audit.emit(
            "patch.apply_fresh",
            agent=ctx.agent.value,
            run_id=ctx.run_id,
            patch_id=patch_id,
            applied=ok,
            out_of_scope=out_of_scope,
            tampered=tampered,
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
            "tampered_protected_tests": tampered,
        }

    @staticmethod
    def _tampered_tests(diff_text: str, protected: list[str]) -> list[str]:
        """Protected test files that the diff modifies or deletes (not merely adds)."""
        protected_set = {safe_rel_path(p) for p in protected}
        touched: list[str] = []
        current: str | None = None
        for line in diff_text.splitlines():
            if line.startswith("diff --git "):
                parts = line.split(" ")
                current = safe_rel_path(parts[3][2:]) if len(parts) > 3 else None
            elif line.startswith("new file mode") and current in protected_set:
                current = None  # a newly added file cannot tamper with an existing one
            elif current in protected_set and (line.startswith("-") and not line.startswith("---")):
                touched.append(current)
                current = None
        return sorted(set(touched))


def recipe_from_snapshot(intel: CodeIntel) -> Any:
    """Recipe provider that reads the target's scope-approved build recipe."""

    def provider(ctx: ToolContext, target_id: str) -> dict[str, Any]:
        path = intel.snapshot.root / "build_recipe.json"
        if not path.is_file():
            raise PlatformError(ErrorCode.SCHEMA_INVALID, "target has no build_recipe.json")
        return json.loads(path.read_text(encoding="utf-8"))

    return provider
