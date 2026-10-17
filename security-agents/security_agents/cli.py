"""Run a scoped seven-agent assessment from the command line.

    python -m security_agents.cli --target ../examples/payments-lite
    python -m security_agents.cli --target ../examples/payments-lite --mode live

`--mode replay` (default) uses the scripted trajectories from the test suite, so
it is reproducible and free; `--mode live` makes real Claude requests and needs
credentials plus `--i-have-authorization`. The printed report always states which
mode produced it.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .agents import ALL_SPECS
from .checks.library import default_library
from .contracts import (
    Approval,
    AuthorizedScope,
    Budget,
    ScopeStatus,
    ScopeTarget,
    new_id,
)
from .intel import LocalIntel
from .llm import FakeLLM, ProviderGateway, live_gateway_from_env
from .sandbox.driver import LocalProcessDriver
from .sandbox.workspace import SnapshotHandle
from .workflow import FindingRecord, Orchestrator, OrchestratorConfig

TARGET_ID = "tgt_demo_target"


def build_scope(*, hours: int = 2, categories: list[str]) -> AuthorizedScope:
    now = datetime.now(UTC)
    return AuthorizedScope(
        id=new_id("scp"),
        project_id="prj_demo",
        name="local demo target",
        targets=[
            ScopeTarget(
                target_id=TARGET_ID,
                repo_id="rep_demo",
                build_recipe_ref="build_recipe.json",
                exposed_ports=[8000],
            )
        ],
        allowed_check_categories=categories,
        status=ScopeStatus.ACTIVE,
        requested_by="usr_operator",
        approved_by="usr_operator",
        approved_at=now,
        expires_at=now + timedelta(hours=hours),
        notes="local owned fixture; sandbox_build target only",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="security_agents.cli", description=__doc__)
    parser.add_argument("--target", required=True, help="path to the owned target repository")
    parser.add_argument("--mode", choices=("replay", "live"), default="replay")
    parser.add_argument("--max-hypotheses", type=int, default=3)
    parser.add_argument("--validate", type=int, default=2, help="hypotheses to validate")
    parser.add_argument("--max-usd", type=float, default=5.0)
    parser.add_argument("--report", type=Path, help="write the JSON report here")
    parser.add_argument("--auto-approve", action="store_true",
                        help="approve remediation automatically (local demo only)")
    parser.add_argument("--i-have-authorization", action="store_true",
                        help="required with --mode live: confirms the target is yours and isolated")
    args = parser.parse_args(argv)

    target = Path(args.target).resolve()
    if not (target / "build_recipe.json").is_file():
        print(f"error: {target} has no build_recipe.json (is it a prepared target?)", file=sys.stderr)
        return 2
    if args.mode == "live" and not args.i_have_authorization:
        print("error: --mode live requires --i-have-authorization", file=sys.stderr)
        return 2

    workdir = Path(tempfile.mkdtemp(prefix="assessment-"))
    snapshot = SnapshotHandle.from_directory(
        target, workdir / "snapshot", snapshot_id=new_id("snp"), repo_id="rep_demo"
    )
    intel = LocalIntel(snapshot)
    library = default_library()
    scope = build_scope(categories=sorted(library.categories()))

    if args.mode == "live":
        gateway = live_gateway_from_env()
    else:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from tests import fake_agents  # scripted trajectories, labelled replay

        gateway = ProviderGateway(FakeLLM(fake_agents.all_scripts(snapshot.root)))

    def approver(finding: FindingRecord) -> Approval | None:
        if finding.plan is None:
            return None
        if not args.auto_approve:
            print("\n--- remediation plan awaiting approval ---")
            print(f"finding: {finding.hypothesis.title}")
            print(f"severity: {finding.severity.level.value if finding.severity else 'n/a'}")
            print(f"strategy: {finding.plan.strategy}")
            print(f"files: {finding.plan.files_expected}")
            answer = input("approve remediation? [y/N] ").strip().lower()
            if answer not in ("y", "yes"):
                return None
        return Approval(
            project_id="prj_demo", subject_type="remediation", subject_id=finding.plan.id,
            decision="approved", decided_by="usr_operator", reason="approved from the CLI",
        )

    config = OrchestratorConfig(
        assessment_id=new_id("asm"),
        project_id="prj_demo",
        org_id="org_demo",
        scope=scope,
        target_id=TARGET_ID,
        requested_by="usr_operator",
        budget=Budget(max_tokens=1_000_000, max_usd=args.max_usd, max_wall_clock_s=1800.0),
        max_hypotheses=args.max_hypotheses,
        max_hypotheses_to_validate=args.validate,
    )
    orchestrator = Orchestrator(
        config,
        intel=intel,
        gateway=gateway,
        driver=LocalProcessDriver(allow=True),
        library=library,
        workdir=workdir / "work",
        approve_remediation=approver,
    )

    print(f"assessment {config.assessment_id} on {target}")
    print(f"provider mode: {gateway.mode}   agents: {len(ALL_SPECS)}   workdir: {workdir}")
    result = orchestrator.run()
    report = result.report()

    print("\n=== states ===")
    print(" -> ".join(report["states"]))
    print("\n=== agent runs ===")
    for run in report["runs"]:
        print(
            f"  {run['agent']:9} {run['status']:9} turns={run['llm_turns']:2} "
            f"tools={run['tool_calls']:2} tokens={run['tokens']:7} ${run['usd']:.4f} "
            f"{run['error_code'] or ''}"
        )
    print("\n=== findings ===")
    for finding in report["findings"]:
        print(f"  [{finding['status']}] {finding['title']}")
        print(
            f"      class={finding['weakness_class']} severity={finding['severity']} "
            f"validation={finding['validation_outcome']} verdicts={finding['verdicts']}"
        )
        for test in finding["regression_tests"]:
            print(f"      regression test: {test}")
        for note in finding["notes"]:
            print(f"      note: {note}")
    print(
        f"\nprovider_modes={report['provider_modes']} "
        f"tokens={report['usage']['input_tokens'] + report['usage']['output_tokens']} "
        f"usd={report['usage']['usd']:.4f} sandbox_s={report['usage']['sandbox_seconds']:.1f}"
    )
    if gateway.mode != "live":
        print("NOTE: model turns were scripted/replayed, not live provider calls.")

    if args.report:
        args.report.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        print(f"report written to {args.report}")
    return 0 if report["state"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
