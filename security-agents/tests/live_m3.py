"""M3 end-to-end acceptance checks over an assessment report (used by the live test and by
scripted contract tests). Each check is separate so a paid run says exactly what failed."""

from __future__ import annotations

from typing import Any

SEVEN_ROLES = ("scout", "probe", "trace", "diagnose", "patch", "verify", "fortify")


def m3_failures(report: dict[str, Any], *, require_live: bool = True) -> list[str]:
    """Return every unmet M3 condition (empty list = M3 met). Never raises on a partial report."""
    failures: list[str] = []
    runs = report.get("runs", [])
    per_role = {role: [r for r in runs if r.get("agent") == role] for role in SEVEN_ROLES}

    # 1. all seven agents were invoked
    missing = [role for role, rs in per_role.items() if not rs]
    if missing:
        failures.append(f"1 invoked: no run for {missing}")
    # live provider turns (live runs only)
    if require_live:
        not_live = [
            role
            for role, rs in per_role.items()
            if rs and not any(r.get("provider_mode") == "live" and r.get("llm_turns", 0) >= 1 for r in rs)
        ]
        if not_live:
            failures.append(f"live: no live model turn for {not_live}")
    # 2. all seven completed successfully (the role's last run succeeded)
    failed = {
        role: (rs[-1].get("error_code"), rs[-1].get("error_detail"))
        for role, rs in per_role.items()
        if rs and rs[-1].get("status") != "succeeded"
    }
    if failed:
        failures.append(f"2 completed: unsuccessful roles {failed}")

    findings = report.get("findings", [])
    confirmed = [f for f in findings if f.get("validation_outcome") == "confirmed"]
    # 3. Probe confirmed a real finding
    if not confirmed:
        failures.append("3 probe: no finding with validation_outcome=confirmed")
    # 4. Patch produced a correction for a confirmed finding
    patched = [f for f in confirmed if f.get("patch_candidates", 0) >= 1]
    if confirmed and not patched:
        failures.append("4 patch: no confirmed finding has a patch candidate")
    # 5. Verify accepted the patched workspace
    accepted = [f for f in patched if "accepted" in f.get("verdicts", [])]
    if patched and not accepted:
        failures.append("5 verify: no patched finding was accepted")
    # 6. Fortify submitted a schema-valid result (run succeeded and the finding was hardened)
    fortify = per_role.get("fortify", [])
    if fortify and fortify[-1].get("status") != "succeeded":
        failures.append(
            f"6 fortify: run {fortify[-1].get('status')} {fortify[-1].get('error_code')}: {fortify[-1].get('error_detail')}"
        )
    if accepted and not any(f.get("status") == "hardened" for f in accepted):
        failures.append("6 fortify: no accepted finding reached status=hardened")
    # 7. the assessment reached its expected terminal state
    if report.get("state") != "completed":
        failures.append(f"7 terminal: state={report.get('state')} (expected completed)")
    return failures
