"""Pure parts of live defense: detection rules, lifecycle, authorization gate, policy
selection (RL vs rule floor), SSRF guard and secret encryption. No network, no database."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet

from backend.live_defense import authorize, netguard, policy, state, vault
from monitoring.detect import Event, detect
from shared.live_defense import DefenseActionKind as K
from shared.live_defense import LiveIncidentState as S

NOW = datetime(2026, 10, 18, 12, 0, tzinfo=UTC)


def ev(i: int, kind: str, ip: str = "203.0.113.7", route: str = "POST /login", **kw) -> Event:
    return Event(
        id=f"sev_{i:08d}",
        kind=kind,
        occurred_at=kw.get("at", NOW - timedelta(seconds=10)),
        source_ip=ip,
        route=route,
        status=kw.get("status"),
        severity=kw.get("severity"),
        controlled_test=True,
    )


# ------------------------------------------------------------------ detection


def test_repeated_auth_failures_open_one_detection_per_source() -> None:
    events = [ev(i, "auth_failure") for i in range(6)] + [ev(9, "auth_failure", ip="198.51.100.2")]
    found = detect(events, NOW)
    assert [(d.rule_id, d.source) for d in found] == [("R1_repeated_auth_failures", "203.0.113.7")]
    d = found[0]
    assert d.correlation_key == "credential_attack|203.0.113.7"
    assert "6 failed sign-ins" in d.rationale and "threshold 5" in d.rationale
    assert len(d.event_ids) == 6


def test_below_threshold_or_outside_window_detects_nothing() -> None:
    assert detect([ev(i, "auth_failure") for i in range(4)], NOW) == []
    old = [ev(i, "auth_failure", at=NOW - timedelta(minutes=10)) for i in range(10)]
    assert detect(old, NOW) == []


def test_scanning_waf_and_error_spike_rules() -> None:
    scan = [ev(i, "not_found", route=f"GET /admin{i}") for i in range(8)]
    waf = [ev(20, "waf_alert", ip="198.51.100.9", severity="critical")]
    errors = [ev(30 + i, "server_error", ip=None) for i in range(10)] + [ev(50, "deploy", ip=None)]
    rules = {d.rule_id: d for d in detect(scan + waf + errors, NOW)}
    assert rules["R2_route_scanning"].source == "203.0.113.7"
    assert rules["R3_high_severity_waf_alert"].severity == "critical"
    spike = rules["R4_server_error_spike"]
    assert spike.source is None and spike.severity == "high" and "deploy" in spike.rationale


# ------------------------------------------------------------------ lifecycle


def test_lifecycle_edges() -> None:
    path = [
        S.DETECTED,
        S.TRIAGED,
        S.RECOMMENDED,
        S.AUTHORIZED,
        S.EXECUTING,
        S.VERIFYING,
        S.RESOLVED,
    ]
    for a, b in zip(path, path[1:], strict=False):
        state.check(a, b)
    state.check(S.RECOMMENDED, S.AWAITING_APPROVAL)
    state.check(S.AWAITING_APPROVAL, S.DENIED)
    state.check(S.RESOLVED, S.ROLLED_BACK)
    for bad in [
        (S.DETECTED, S.EXECUTING),
        (S.DENIED, S.AUTHORIZED),
        (S.ESCALATED, S.RESOLVED),
        (S.ROLLED_BACK, S.RESOLVED),
    ]:
        with pytest.raises(state.IllegalTransition):
            state.check(*bad)


# ------------------------------------------------------------------ authorization gate

APP = authorize.AppFacts(
    enabled=True, auto_response=True, protected_sources=frozenset({"198.51.100.1"})
)
GRANTS = {K.block_source: authorize.Grant(max_duration_s=900, hourly_budget=2)}


def gate(
    kind=K.block_source,
    target="203.0.113.7",
    duration=600,
    app=APP,
    grants=GRANTS,
    used=None,
    mode="automatic",
):
    return authorize.check(
        authorize.Proposal(kind, target, duration), app, grants, used or {}, mode
    )


def test_pre_authorized_block_passes_every_check() -> None:
    r = gate()
    assert r.outcome == "authorized" and r.reason_code == "PRE_AUTHORIZED"
    assert all(c.passed for c in r.checks)


@pytest.mark.parametrize(
    ("target", "code"),
    [
        ("127.0.0.1", "UNSAFE_TARGET"),
        ("169.254.10.1", "UNSAFE_TARGET"),
        ("0.0.0.0", "UNSAFE_TARGET"),
        ("224.0.0.1", "UNSAFE_TARGET"),
        ("203.0.113.0/24", "UNSAFE_TARGET"),
        ("198.51.100.1", "UNSAFE_TARGET"),
        ("not-an-ip", "UNSAFE_TARGET"),
        ("::ffff:127.0.0.1", "UNSAFE_TARGET"),
    ],
)
def test_blast_radius_is_a_hard_denial(target: str, code: str) -> None:
    r = gate(target=target)
    assert r.outcome == "denied" and r.reason_code == code


def test_soft_failures_route_to_a_person() -> None:
    assert gate(app=authorize.AppFacts(True, False)).reason_code == "AUTO_RESPONSE_OFF"
    assert gate(grants={}).reason_code == "NO_GRANT"
    assert gate(duration=1200).reason_code == "DURATION_ABOVE_GRANT"
    r = gate(used={K.block_source: 2})
    assert r.outcome == "requires_human" and r.reason_code == "BUDGET_EXHAUSTED"


def test_human_approval_still_enforces_hard_checks() -> None:
    assert (
        gate(grants={}, app=authorize.AppFacts(True, False), mode="human").outcome == "authorized"
    )
    assert gate(target="127.0.0.1", mode="human").outcome == "denied"
    assert gate(duration=25 * 3600, mode="human").outcome == "denied"
    assert gate(app=authorize.AppFacts(False, True), mode="human").reason_code == "APP_DISABLED"


def test_internal_kinds_execute_nothing_and_none_is_not_applicable() -> None:
    assert gate(kind=K.escalate, target=None, duration=None).reason_code == "INTERNAL_ONLY"
    assert gate(kind=None).outcome == "not_applicable"


# ------------------------------------------------------------------ policy: RL vs rules


def facts(**kw) -> policy.IncidentFacts:
    base = dict(
        project_id="prj_TESTPROJECT01",
        category="credential_attack",
        source="203.0.113.7",
        severity="medium",
        event_count=6,
        routes=("POST /login",),
        last_event_at=NOW - timedelta(seconds=5),
        now=NOW,
    )
    return policy.IncidentFacts(**{**base, **kw})


class Runner:
    """TEST runner: stands in for the checkpoint and is labelled as such."""

    policy_version = "TEST-RUNNER"
    checkpoint_sha256 = "0" * 64

    def __init__(self, action: str) -> None:
        self.action = action

    def recommend(self, f):  # noqa: ANN001
        scores = [
            SimpleNamespace(action=self.action, node="auth", q_value=1.5),
            SimpleNamespace(action="noop", node=None, q_value=0.4),
        ]
        return SimpleNamespace(
            action=self.action,
            node="auth",
            q_margin=1.1,
            top_actions=scores,
            policy_version=self.policy_version,
            checkpoint_sha256=self.checkpoint_sha256,
        )


@pytest.fixture
def runner(monkeypatch: pytest.MonkeyPatch):
    def use(action: str | None) -> None:
        monkeypatch.setattr(policy, "RUNNER_OVERRIDE", Runner(action) if action else None)

    return use


def test_without_a_checkpoint_the_rules_decide_and_say_so(runner) -> None:
    runner(None)
    rl, rule, final = policy.decide(facts())
    assert rl.status == "unavailable" and "RL_CHECKPOINT_PATH" in rl.reason
    assert final.kind is K.block_source and final.selected_by == "rules"
    assert final.reason.startswith("deterministic fallback")


def test_rl_noop_never_takes_credit_for_the_rule_block(runner) -> None:
    runner("noop")
    rl, rule, final = policy.decide(facts())
    assert rl.status == "ok" and rl.action == "noop" and rl.mapped_kind is None
    assert final.kind is K.block_source and final.selected_by == "rules"
    assert rl.top_actions[0].q_value == 1.5 and rl.observation_provenance["focus_node"] == "auth"


def test_rl_stronger_than_floor_is_credited_to_rl(runner) -> None:
    runner("rate_limit")
    rl, _, final = policy.decide(
        facts(category="error_spike", source=None, routes=("POST /login",))
    )
    assert (
        rl.mapped_kind is K.rate_limit
        and final.selected_by == "rl"
        and final.target == "POST /login"
    )


def test_isolate_is_never_mapped_and_stale_input_is_rejected(runner) -> None:
    runner("isolate")
    rl, _, final = policy.decide(facts())
    assert rl.mapped_kind is None and "never executed" in (rl.mapping_note or "")
    assert final.selected_by == "rules"
    rl, _, final = policy.decide(facts(last_event_at=NOW - timedelta(hours=1)))
    assert rl.status == "rejected_input" and "stale" in rl.reason and final.selected_by == "rules"


# ------------------------------------------------------------------ SSRF guard


@pytest.fixture
def dns(monkeypatch: pytest.MonkeyPatch, settings_override):
    answers: dict[str, list[str]] = {}
    monkeypatch.setattr(
        netguard, "RESOLVER", lambda host, port: answers.get(host, ["93.184.216.34"])
    )
    settings_override(app_env="production", live_defense_allowed_private_hosts="127.0.0.1:8765")
    return answers


@pytest.mark.parametrize(
    "url",
    [
        "https://169.254.169.254/latest/meta-data/",
        "https://[fd00:ec2::254]/",
        "https://127.0.0.1/",
        "https://10.0.0.5/",
        "https://[::1]/",
        "https://[::ffff:127.0.0.1]/",
        "https://user:pw@example.com/",
        "ftp://example.com/",
        "file:///etc/passwd",
        "http://example.com/",  # plain http outside development
        "https://127.0.0.1:8766/",  # allowlist is exact host:port
    ],
)
def test_unsafe_destinations_are_refused(dns, url: str) -> None:
    with pytest.raises(netguard.UnsafeDestination):
        netguard.check_url(url)


def test_dns_names_are_checked_by_every_resolved_address(dns) -> None:
    dns["rebind.example"] = ["93.184.216.34", "127.0.0.1"]
    dns["metadata.example"] = ["169.254.169.254"]
    for host in ("rebind.example", "metadata.example"):
        with pytest.raises(netguard.UnsafeDestination):
            netguard.check_url(f"https://{host}/hook")
    ok = netguard.check_url("https://hooks.example/notify?x=1")
    assert ok.address == "93.184.216.34" and ok.path_query == "/notify?x=1"


def test_allowlisted_owned_test_host_but_never_metadata(dns, settings_override) -> None:
    assert netguard.check_url("http://127.0.0.1:8765/ari").address == "127.0.0.1"
    settings_override(live_defense_allowed_private_hosts="169.254.169.254:80")
    with pytest.raises(netguard.UnsafeDestination):
        netguard.check_url("http://169.254.169.254/")


def test_redirects_are_not_followed(monkeypatch: pytest.MonkeyPatch, settings_override) -> None:
    import httpx

    settings_override(app_env="test", live_defense_allowed_private_hosts="127.0.0.1:9")
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(302, headers={"Location": "http://169.254.169.254/"})

    real = httpx.Client

    def client(**kw):
        return real(transport=httpx.MockTransport(handler), **kw)

    monkeypatch.setattr(netguard.httpx, "Client", client)
    resp = netguard.request("POST", "http://127.0.0.1:9/hook", content=b"{}")
    assert resp.status_code == 302 and len(seen) == 1
    assert seen[0].url.host == "127.0.0.1" and seen[0].headers["host"] == "127.0.0.1:9"


# ------------------------------------------------------------------ secrets at rest


def test_signing_secrets_encrypt_and_fail_closed(settings_override) -> None:
    settings_override(live_defense_secret_key="")
    with pytest.raises(vault.SecretKeyUnavailable):
        vault.encrypt("x")
    settings_override(live_defense_secret_key=Fernet.generate_key().decode())
    secret = vault.new_signing_secret()
    token = vault.encrypt(secret)
    assert secret not in token and vault.decrypt(token) == secret
    settings_override(live_defense_secret_key=Fernet.generate_key().decode())
    with pytest.raises(vault.SecretKeyUnavailable):
        vault.decrypt(token)  # a different key cannot read it
    sig = vault.sign(secret, "1700000000", b"body")
    assert vault.verify(secret, "1700000000", b"body", sig)
    assert not vault.verify(secret, "1700000001", b"body", sig)
