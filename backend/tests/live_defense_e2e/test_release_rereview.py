"""Independent release probes; real DB, owned fixture, scripted provider only."""

import os

import sqlalchemy as sa

from backend import execution
from backend.db import get_engine, transaction
from backend.db import jobs as jobs_t

from .test_independent_integration import jobrow, prepare
from .transports import gateway_factory


def test_abrupt_process_death_during_provider_send_requires_recovery(staging):
    alice, app, _repo = prepare(staging)

    class ExitAtSend:
        mode = "fake"

        def complete(self, request):
            os._exit(71)  # cannot run BaseException handlers, like a killed worker

    staging.use_gateway(gateway_factory(ExitAtSend()))
    assert staging.ingest(alice, app).status_code == 202
    staging.drain(kinds=["live_defense_shadow", "live_defense_first_responder"])
    pid = os.fork()
    if pid == 0:
        get_engine().dispose(close=False)
        try:
            staging.drain(kinds=["live_defense_agent_step"])
        finally:
            os._exit(72)
    _, status = os.waitpid(pid, 0)
    assert os.waitstatus_to_exitcode(status) == 71
    step = next(j for j in staging.job_rows("live_defense_agent_step") if j["status"] == "running")
    with transaction() as conn:
        conn.execute(
            sa.update(jobs_t)
            .where(jobs_t.c.id == step["id"])
            .values(lease_expires_at=sa.func.now() - sa.text("interval '1 second'"))
        )
        execution.reconcile(conn)
    assert jobrow(step["id"])["status"] == "recovery_required"


def test_repo_picker_does_not_disclose_other_tenant_connection(client_factory):
    from backend.db import github_repo_access

    alice, bob = client_factory("alice"), client_factory("bob")
    pid = alice.post("/api/v1/projects", json={"name": "alice-private"}).json()["id"]
    rid = alice.post(
        f"/api/v1/projects/{pid}/repositories",
        json={"full_name": "acme/payments", "installation_id": None},
    ).json()["id"]
    with transaction() as conn:
        conn.execute(
            sa.insert(github_repo_access).values(
                user_id=bob.me["user"]["id"],
                full_name="acme/payments",
                installation_id=123,
                default_branch="main",
                private=True,
            )
        )
    assert bob.get(f"/api/v1/repositories/{rid}").status_code == 404
    rows = bob.get("/api/v1/github/repositories").json()["items"]
    assert rows[0]["connected_repo_id"] is None


def test_reconnect_refuses_stale_access_when_fresh_check_fails(client_factory, monkeypatch):
    import httpx

    from backend.db import github_repo_access, repositories, users

    alice = client_factory("alice")
    pid = alice.post("/api/v1/projects", json={"name": "private"}).json()["id"]
    rid = alice.post(
        f"/api/v1/projects/{pid}/repositories",
        json={"full_name": "acme/payments", "installation_id": None},
    ).json()["id"]
    uid = alice.me["user"]["id"]
    with transaction() as conn:
        conn.execute(
            sa.update(repositories).where(repositories.c.id == rid).values(installation_id=123)
        )
        conn.execute(
            sa.update(users).where(users.c.id == uid).values(github_login="alice", github_id=12345)
        )
        conn.execute(
            sa.insert(github_repo_access).values(
                user_id=uid,
                full_name="acme/payments",
                installation_id=123,
                default_branch="main",
                private=True,
            )
        )
    assert alice.post(f"/api/v1/repositories/{rid}/disconnect").status_code == 200

    def revoked(self, login):
        raise httpx.HTTPStatusError(
            "installation revoked",
            request=httpx.Request("GET", "https://api.github.com/users/alice/installation"),
            response=httpx.Response(404),
        )

    class RevokedApp:
        user_installation = revoked

    monkeypatch.setattr("backend.api.github_repos.GitHubApp", RevokedApp)
    result = alice.post(f"/api/v1/repositories/{rid}/reconnect")
    assert result.status_code in {403, 503}, result.text


def test_repository_disconnect_stops_next_provider_turn(staging):
    from .transports import fake_provider

    alice, app, repo = prepare(staging)
    fake = fake_provider(repo / "target")

    class DisconnectDuringTurn:
        mode = "fake"
        calls = 0

        def complete(self, request):
            self.calls += 1
            response = fake.complete(request)
            if self.calls == 1:
                result = alice.post(f"/api/v1/repositories/{app.repo_id}/disconnect")
                assert result.status_code == 200, result.text
            return response

    provider = DisconnectDuringTurn()
    staging.use_gateway(gateway_factory(provider))
    assert staging.ingest(alice, app).status_code == 202
    staging.drain()
    assert provider.calls == 1, f"provider turns after repository disconnect: {provider.calls - 1}"
