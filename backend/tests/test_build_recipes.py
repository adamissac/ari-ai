"""Build-recipe generator (backend.recipes): inspection, drafting, validation and the PR job.

Repositories are real git repositories in tmp_path; the "GitHub" remote is a local bare
repository reached over file://, so fetch, ls-remote and push run real git. Only the GitHub
App (tokens, opening the PR) is faked. Claude turns are a scripted FakeTransport."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
import sqlalchemy as sa
from helpers import post_webhook

from backend import llm, recipes, worker
from backend.db import audit_events, github_repo_access, jobs, repositories, transaction

ROOT = Path(__file__).resolve().parents[2]
SHOP = {
    "src/shop/__init__.py": "",
    "src/shop/main.py": (
        "from fastapi import FastAPI\n\nfrom shop import orders\n\napp = FastAPI()\n"
        'app.include_router(orders.router, prefix="/api")\n'
    ),
    "src/shop/orders.py": (
        "from fastapi import APIRouter, Depends\n\n"
        'router = APIRouter(prefix="/orders")\n\n\n'
        "def current_user():\n    return None\n\n\n"
        '@router.get("/{order_id}")\n'
        "def read_order(order_id: str, user=Depends(current_user)):\n"
        "    return find_order(order_id, user)\n\n\n"
        '@router.get("/")\ndef list_orders():\n    return []\n'
    ),
    "tests/test_orders.py": "def test_x():\n    assert True\n",
    "requirements.txt": "fastapi>=0.100\nsqlalchemy==2.0.30\nrequests>=2\n",
}


def _git(*args: str, cwd: Path) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def _repo(path: Path, files: dict[str, str]) -> tuple[Path, str]:
    for rel, content in files.items():
        (path / rel).parent.mkdir(parents=True, exist_ok=True)
        (path / rel).write_text(content)
    _git("init", "-q", "-b", "main", cwd=path)
    _git("add", "-A", cwd=path)
    _git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init", cwd=path)
    return path, _git("rev-parse", "HEAD", cwd=path)


def _payments_lite(tmp_path: Path) -> tuple[Path, str]:
    src = tmp_path / "pl"
    shutil.copytree(
        ROOT / "examples/payments-lite/target", src, ignore=shutil.ignore_patterns("__pycache__")
    )
    return _repo(src, {})


def test_payments_lite_needs_no_harness(tmp_path) -> None:
    repo, sha = _payments_lite(tmp_path)
    facts = recipes.inspect(repo, sha)
    assert facts.app and facts.app["module"] == "payments_lite.app"
    assert ("GET", "/payments/{payment_id}") in facts.route_keys()
    d = recipes.draft(facts)
    assert d.recipe["app_factory"] == "payments_lite.app:create_app"
    assert d.recipe["test_command"] == ["-q", "tests"] and d.harness is None
    assert d.recipe["sandbox"]["pip"] == []  # fastapi/uvicorn/pydantic ship with the runner
    assert recipes.problems(d.recipe, d.harness, facts) == []


def test_src_layout_module_app_gets_a_wrapper_prefixes_and_pins(tmp_path) -> None:
    repo, sha = _repo(tmp_path / "shop", SHOP)
    facts = recipes.inspect(repo, sha)
    assert facts.app == {
        "path": "src/shop/main.py",
        "attr": "app",
        "factory": False,
        "module": "shop.main",
        "source_root": "src",
    }
    assert ("GET", "/api/orders/{order_id}") in facts.route_keys()
    route = next(r for r in facts.routes if r["path_template"] == "/api/orders/{order_id}")
    assert route["ownership_signal"]
    assert facts.pins == ["sqlalchemy==2.0.30"] and facts.unpinned == ["requests"]
    d = recipes.draft(facts)
    assert d.recipe["app_factory"] == "deploy.sandbox_target:create_app"
    assert '/ "src"' in d.harness and "from shop.main import app" in d.harness
    assert any("requests" in n for n in d.notes)
    assert recipes.problems(d.recipe, d.harness, facts) == []


def _submit(proposal: dict, n: int) -> dict:
    return {
        "content": [
            {"type": "tool_use", "id": f"t{n}", "name": "submit_result", "input": proposal}
        ],
        "stop_reason": "tool_use",
    }


HARNESS = (
    "import sys\n\nTOKENS = {'sbx-alice': 'u1', 'sbx-bob': 'u2'}\n"
    "ORDERS = {'ord_a': 'u1', 'ord_b': 'u2'}\n\n\ndef create_app():\n"
    "    from shop.main import app\n\n    return app\n"
)
GOOD = {
    "app_factory": "deploy.sandbox_target:create_app",
    "harness_source": HARNESS,
    "identities": {"alice": "Bearer sbx-alice", "bob": "Bearer sbx-bob"},
    "resources": {"order": {"alice": "ord_a", "bob": "ord_b"}},
    "routes": [
        {
            "id": "order_detail",
            "method": "GET",
            "path_template": "/api/orders/{order_id}",
            "resource": "order",
        }
    ],
}


def test_claude_completes_the_recipe_and_invalid_proposals_are_sent_back(tmp_path) -> None:
    repo, sha = _repo(tmp_path / "shop", SHOP)
    facts = recipes.inspect(repo, sha)
    bad = GOOD | {"routes": [GOOD["routes"][0] | {"path_template": "/orders/{order_id}"}]}
    transport = llm.FakeTransport(
        [
            {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "r1",
                        "name": "search",
                        "input": {"pattern": "def current_user"},
                    }
                ],
                "stop_reason": "tool_use",
            },
            _submit(bad, 2),
            _submit(GOOD, 3),
        ]
    )
    d = recipes.draft(facts, llm.build_gateway(transport=transport))
    assert d.author == "claude"
    assert d.recipe["routes"][0]["path_template"] == "/api/orders/{order_id}"
    assert d.recipe["identities"]["bob"] == {"auth_header": "Bearer sbx-bob"}
    assert recipes.problems(d.recipe, d.harness, facts) == []
    sent = json.dumps(transport.requests[2]["messages"][-1])
    assert "src/shop/orders.py:6: def current_user" in json.dumps(transport.requests[1]["messages"])
    assert "not in the code-intelligence index" in sent


def test_a_model_that_never_validates_falls_back_to_the_deterministic_recipe(tmp_path) -> None:
    repo, sha = _repo(tmp_path / "shop", SHOP)
    facts = recipes.inspect(repo, sha)
    unseeded = GOOD | {"resources": {"order": {"alice": "ord_x", "bob": "ord_b"}}}
    gw = llm.build_gateway(transport=llm.FakeTransport([_submit(unseeded, i) for i in range(3)]))
    d = recipes.draft(facts, gw)
    assert d.author == "heuristic" and d.recipe["routes"] == []
    assert any("Claude could not draft" in n for n in d.notes)


@pytest.mark.parametrize(
    ("change", "error"),
    [
        ({"sandbox": {"pip": ["requests"], "apt": [], "include": []}}, "not allowed"),
        ({"app_factory": "shop.main:missing"}, "is not defined"),
        ({"test_roots": ["nope"]}, "has no files"),
    ],
)
def test_problems_rejects(tmp_path, change, error) -> None:
    repo, sha = _repo(tmp_path / "shop", SHOP)
    facts = recipes.inspect(repo, sha)
    d = recipes.draft(facts)
    assert any(error in p for p in recipes.problems(d.recipe | change, d.harness, facts))


def test_problems_requires_seeded_identities_for_every_route(tmp_path) -> None:
    repo, sha = _repo(tmp_path / "shop", SHOP)
    facts = recipes.inspect(repo, sha)
    d = recipes.merge(recipes.base_recipe(facts), recipes.Proposal.model_validate(GOOD))
    assert recipes.problems(d.recipe, d.harness, facts) == []
    one = d.recipe | {"resources": {"order": {"alice": {"id": "ord_a"}}}}
    assert any("no id for bob" in p for p in recipes.problems(one, d.harness, facts))
    assert any(
        "never seeded" in p for p in recipes.problems(d.recipe, "def create_app(): ...", facts)
    )


# --------------------------------------------------------------------------- job + triggers


class FakeApp:
    prs: list[dict] = []

    def __init__(self, settings=None) -> None: ...

    def installation_token(self, installation_id, *, write=False, repository=None) -> str:
        assert installation_id == 7 and (not write or repository == "shop")
        return "tok"

    def open_pull_request(self, installation_id, full_name, **kw) -> str:
        FakeApp.prs.append({"full_name": full_name, **kw})
        return f"https://github.com/{full_name}/pull/1"


@pytest.fixture
def github(tmp_path, settings_override, monkeypatch):
    """A file:// "GitHub" holding acme/shop; returns a function publishing files to it."""
    remote = tmp_path / "remote"
    settings_override(security_workdir=str(tmp_path / "work"), github_web_url=f"file://{remote}")
    FakeApp.prs = []
    monkeypatch.setattr("backend.github.GitHubApp", FakeApp)
    monkeypatch.setattr(recipes, "gateway_or_none", lambda: None)

    def publish(files: dict[str, str]) -> Path:
        src, _ = _repo(tmp_path / "src", files)
        bare = remote / "acme/shop.git"
        _git("init", "-q", "--bare", str(bare), cwd=tmp_path)
        _git("push", "-q", str(bare), "main", cwd=src)
        return bare

    return publish


def _connect(client, installation_id: int | None = 7) -> str:
    pid = client.post("/api/v1/projects", json={"name": "shop"}).json()["id"]
    with transaction() as conn:
        conn.execute(
            sa.insert(github_repo_access).values(
                user_id=client.me["user"]["id"], full_name="acme/shop", installation_id=7,
                default_branch="main", private=True,
            )
        )  # fmt: skip
    r = client.post(
        f"/api/v1/projects/{pid}/repositories",
        json={"full_name": "acme/shop", "installation_id": installation_id},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _audit(action: str) -> list[dict]:
    with transaction() as conn:
        docs = conn.execute(sa.select(audit_events.c.doc)).scalars()
        return [d["details"] for d in docs if d["action"] == action]


def test_connecting_a_repo_opens_a_recipe_pr_never_on_main(client_factory, github) -> None:
    bare = github(SHOP)
    main_before = _git("rev-parse", "main", cwd=bare)
    _connect(client_factory("alice"))
    worker.drain(kinds=["propose_build_recipe"])
    assert [(p["head"], p["base"]) for p in FakeApp.prs] == [("ari/build-recipe", "main")]
    assert "build_recipe.json" in FakeApp.prs[0]["body"]
    assert _git("rev-parse", "main", cwd=bare) == main_before
    shown = json.loads(_git("show", "ari/build-recipe:build_recipe.json", cwd=bare))
    assert shown["app_factory"] == "deploy.sandbox_target:create_app"
    assert "from shop.main import app" in _git(
        "show", "ari/build-recipe:deploy/sandbox_target.py", cwd=bare
    )
    assert _audit("recipe.pr_opened")[0]["url"] == "https://github.com/acme/shop/pull/1"


def test_a_repo_with_a_recipe_is_left_alone(client_factory, github) -> None:
    bare = github(SHOP | {"build_recipe.json": "{}\n"})
    _connect(client_factory("alice"))
    worker.drain(kinds=["propose_build_recipe"])
    assert FakeApp.prs == [] and _audit("recipe.skipped")
    assert "ari/build-recipe" not in _git("branch", "--list", cwd=bare)


def test_repos_without_the_app_are_not_queued(client_factory) -> None:
    _connect(client_factory("alice"), installation_id=None)
    with transaction() as conn:
        assert "propose_build_recipe" not in conn.execute(sa.select(jobs.c.kind)).scalars().all()


def test_installation_webhook_queues_already_connected_repos(client_factory) -> None:
    alice = client_factory("alice")
    rid = _connect(alice)
    with transaction() as conn:
        conn.execute(sa.delete(jobs))
    added = {
        "action": "added",
        "installation": {"id": 7},
        "repositories_added": [{"full_name": "acme/shop"}, {"full_name": "acme/other"}],
    }
    assert post_webhook(alice, added, event="installation_repositories").status_code == 202
    worker.drain(kinds=["process_github_delivery"])
    with transaction() as conn:
        queued = (
            conn.execute(sa.select(jobs.c.payload).where(jobs.c.kind == "propose_build_recipe"))
            .scalars()
            .all()
        )
        assert queued == [{"repo_id": rid}]
        conn.execute(sa.update(repositories).values(installation_id=None))
    post_webhook(alice, added | {"action": "removed"}, event="installation_repositories")
    worker.drain(kinds=["process_github_delivery"])
    with transaction() as conn:
        assert (
            len(
                conn.execute(
                    sa.select(jobs.c.id).where(jobs.c.kind == "propose_build_recipe")
                ).all()
            )
            == 1
        )
