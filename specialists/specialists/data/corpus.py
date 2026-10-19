"""Synthetic, reproducible web-handler corpus: vulnerable and fixed variants per CWE family.

Every sample is generated from a seeded RNG, so the corpus is reproducible from (generator
version, seed) and its SHA-256 is recorded in each checkpoint manifest. No customer or third-party
repository code is used. Each CWE class has four *families* (structurally different code shapes,
e.g. an ORM lookup vs a raw cursor vs a repository helper); splits are by family, so the test set
measures generalisation to a code shape the model never saw, not memorisation of a template.

Each family yields, per sample, the vulnerable code, the minimal fixed code, an incomplete fix,
and the labels the downstream agents train on: root-cause class (Diagnose), remediation strategy
(Patch), validation strategy (Probe).
"""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass

GENERATOR_VERSION = "corpus-2"

RESOURCES = [
    "invoice",
    "order",
    "document",
    "payment",
    "ticket",
    "profile",
    "project",
    "report",
    "note",
    "shipment",
    "contract",
    "account",
    "booking",
    "message",
    "upload",
    "claim",
]
USERS = ["user", "current_user", "caller", "principal", "actor", "me"]
FRAMEWORKS = ["fastapi", "flask", "express"]


@dataclass
class Sample:
    family: str
    cwe: str  # weakness class of the vulnerable variant
    framework: str
    vulnerable: str
    fixed: str
    partial: str  # an incomplete or wrong fix (for Verify)
    cause: str  # Diagnose label (CauseClass value)
    strategy: str  # Patch label
    probe: str  # Probe validation strategy label
    observation: str  # what validation would observe (for Diagnose)


class Ctx:
    """Random names for one sample."""

    def __init__(self, rng: random.Random, framework: str) -> None:
        self.rng = rng
        self.fw = framework
        self.res = rng.choice(RESOURCES)
        self.Res = self.res.capitalize()
        self.user = rng.choice(USERS)
        self.idv = rng.choice(
            [
                f"{self.res}_id",
                "item_id",
                "pk",
                "id",
                f"{self.res}Id" if framework == "express" else "obj_id",
            ]
        )
        self.table = self.res + rng.choice(["s", "s", "_records", "_table"])
        self.fn = rng.choice(["get", "read", "fetch", "show", "load", "view"]) + "_" + self.res
        self.var = rng.choice(["row", "obj", "item", "record", "result", self.res])
        self.db = rng.choice(["db", "session", "conn", "store"])
        self.owner = rng.choice(["owner_id", "user_id", "created_by", "tenant_id", "account_id"])

    def pick(self, *options: str) -> str:
        return self.rng.choice(options)

    def noise(self) -> str:
        return self.rng.choice(
            [
                "",
                "",
                f'    log.info("{self.fn} called")\n',
                "    # TODO: add caching\n",
                f"    metrics.increment('{self.res}.read')\n",
                '    """Return the requested resource."""\n',
            ]
        )


def py_route(c: Ctx, method: str, path: str, params: str, body: str, *, auth: bool = True) -> str:
    """Wrap a body in a FastAPI or Flask handler (or an Express one for JS bodies)."""
    if c.fw == "fastapi":
        dep = f", {c.user}: User = Depends(get_current_user)" if auth else ""
        return (
            f'@router.{method.lower()}("{path}")\n'
            f"async def {c.fn}({params}{dep}):\n{c.noise()}{body}"
        )
    deco = f'@app.route("{path.replace("{", "<").replace("}", ">")}", methods=["{method}"])\n'
    login = "@login_required\n" if auth else ""
    head = f"def {c.fn}({params.split(':')[0] if params else ''}):\n"
    pre = f"    {c.user} = g.user\n" if auth else ""
    return f"{deco}{login}{head}{c.noise()}{pre}{body}"


def js_route(c: Ctx, method: str, path: str, body: str, *, auth: bool = True) -> str:
    mw = c.pick("requireAuth, ", "authenticate, ", "ensureLoggedIn, ") if auth else ""
    p = path.replace("{", ":").replace("}", "")
    return f"router.{method.lower()}('{p}', {mw}async (req, res) => {{\n{body}}});\n"


Family = Callable[[Ctx], Sample]
FAMILIES: dict[str, list[Family]] = {}


def family(cwe: str):
    def wrap(fn: Family) -> Family:
        FAMILIES.setdefault(cwe, []).append(fn)
        return fn

    return wrap


def _uid(c: Ctx) -> str:
    return "req.user.id" if c.fw == "express" else f"{c.user}.id"


# ----------------------------------------------------------------- CWE-639 IDOR


@family("CWE-639")
def idor_orm(c: Ctx) -> Sample:
    path = f"/{c.res}s/{{{c.idv}}}"
    if c.fw == "express":
        v = js_route(
            c,
            "GET",
            path,
            f"  const {c.var} = await {c.Res}.findByPk(req.params.{c.idv});\n  if (!{c.var}) return res.sendStatus(404);\n  res.json({c.var});\n",
        )
        f = js_route(
            c,
            "GET",
            path,
            f"  const {c.var} = await {c.Res}.findOne({{ where: {{ id: req.params.{c.idv}, {c.owner}: req.user.id }} }});\n  if (!{c.var}) return res.sendStatus(404);\n  res.json({c.var});\n",
        )
        p = js_route(
            c,
            "GET",
            path,
            f"  const {c.var} = await {c.Res}.findByPk(req.params.{c.idv});\n  if (!{c.var}) return res.sendStatus(404);\n  if (req.query.check) {{ if ({c.var}.{c.owner} !== req.user.id) return res.sendStatus(404); }}\n  res.json({c.var});\n",
        )
    else:
        q = f"{c.db}.query({c.Res}).filter({c.Res}.id == {c.idv})"
        v = py_route(
            c,
            "GET",
            path,
            f"{c.idv}: int",
            f"    {c.var} = {q}.first()\n    if {c.var} is None:\n        raise NotFound()\n    return {c.var}\n",
        )
        f = py_route(
            c,
            "GET",
            path,
            f"{c.idv}: int",
            f"    {c.var} = {q}.filter({c.Res}.{c.owner} == {c.user}.id).first()\n    if {c.var} is None:\n        raise NotFound()\n    return {c.var}\n",
        )
        p = py_route(
            c,
            "GET",
            path,
            f"{c.idv}: int",
            f"    {c.var} = {q}.first()\n    if {c.var} is None or ({c.var}.{c.owner} != {c.user}.id and {c.var}.public):\n        raise NotFound()\n    return {c.var}\n",
        )
    return Sample(
        "idor_orm",
        "CWE-639",
        c.fw,
        v,
        f,
        p,
        "missing_check",
        "add_ownership_predicate",
        "WSTG-ATHZ-04",
        f"user B received user A's {c.res} (200) for GET {path}",
    )


@family("CWE-639")
def idor_sql(c: Ctx) -> Sample:
    path = f"/api/{c.res}s/{{{c.idv}}}"
    if c.fw == "express":
        v = js_route(
            c,
            "GET",
            path,
            f"  const {{ rows }} = await pool.query('SELECT * FROM {c.table} WHERE id = $1', [req.params.{c.idv}]);\n  res.json(rows[0] || null);\n",
        )
        f = js_route(
            c,
            "GET",
            path,
            f"  const {{ rows }} = await pool.query('SELECT * FROM {c.table} WHERE id = $1 AND {c.owner} = $2', [req.params.{c.idv}, req.user.id]);\n  res.json(rows[0] || null);\n",
        )
        p = js_route(
            c,
            "GET",
            path,
            f"  const {{ rows }} = await pool.query('SELECT * FROM {c.table} WHERE id = $1 OR {c.owner} = $2', [req.params.{c.idv}, req.user.id]);\n  res.json(rows[0] || null);\n",
        )
    else:
        v = py_route(
            c,
            "GET",
            path,
            f"{c.idv}: int",
            f'    cur = {c.db}.execute("SELECT * FROM {c.table} WHERE id = ?", ({c.idv},))\n    return cur.fetchone()\n',
        )
        f = py_route(
            c,
            "GET",
            path,
            f"{c.idv}: int",
            f'    cur = {c.db}.execute("SELECT * FROM {c.table} WHERE id = ? AND {c.owner} = ?", ({c.idv}, {c.user}.id))\n    return cur.fetchone()\n',
        )
        p = py_route(
            c,
            "GET",
            path,
            f"{c.idv}: int",
            f'    cur = {c.db}.execute("SELECT * FROM {c.table} WHERE id = ? OR {c.owner} = ?", ({c.idv}, {c.user}.id))\n    return cur.fetchone()\n',
        )
    return Sample(
        "idor_sql",
        "CWE-639",
        c.fw,
        v,
        f,
        p,
        "missing_check",
        "add_ownership_predicate",
        "WSTG-ATHZ-04",
        f"second identity read a {c.res} row it does not own",
    )


@family("CWE-639")
def idor_repo(c: Ctx) -> Sample:
    path = f"/{c.res}s/{{{c.idv}}}/download"
    helper = c.pick("repo", "service", "storage")
    if c.fw == "express":
        v = js_route(
            c,
            "GET",
            path,
            f"  const file = await {helper}.load{c.Res}(req.params.{c.idv});\n  res.send(file.content);\n",
        )
        f = js_route(
            c,
            "GET",
            path,
            f"  const file = await {helper}.load{c.Res}(req.params.{c.idv});\n  if (!file || file.{c.owner} !== req.user.id) return res.sendStatus(404);\n  res.send(file.content);\n",
        )
        p = js_route(
            c,
            "GET",
            path,
            f"  const file = await {helper}.load{c.Res}(req.params.{c.idv});\n  if (!file) return res.sendStatus(404);\n  res.send(file.content);\n",
        )
    else:
        v = py_route(
            c,
            "GET",
            path,
            f"{c.idv}: str",
            f"    blob = {helper}.load_{c.res}({c.idv})\n    return Response(blob.content)\n",
        )
        f = py_route(
            c,
            "GET",
            path,
            f"{c.idv}: str",
            f"    blob = {helper}.load_{c.res}({c.idv})\n    if blob is None or blob.{c.owner} != {c.user}.id:\n        raise NotFound()\n    return Response(blob.content)\n",
        )
        p = py_route(
            c,
            "GET",
            path,
            f"{c.idv}: str",
            f"    blob = {helper}.load_{c.res}({c.idv})\n    if blob is None:\n        raise NotFound()\n    return Response(blob.content)\n",
        )
    return Sample(
        "idor_repo",
        "CWE-639",
        c.fw,
        v,
        f,
        p,
        "missing_check",
        "check_owner_after_load",
        "WSTG-ATHZ-04",
        f"download of another tenant's {c.res} succeeded",
    )


@family("CWE-639")
def idor_update(c: Ctx) -> Sample:
    path = f"/{c.res}s/{{{c.idv}}}"
    field = c.pick("title", "status", "notes", "amount")
    if c.fw == "express":
        v = js_route(
            c,
            "PATCH",
            path,
            f"  await {c.Res}.update({{ {field}: req.body.{field} }}, {{ where: {{ id: req.params.{c.idv} }} }});\n  res.sendStatus(204);\n",
        )
        f = js_route(
            c,
            "PATCH",
            path,
            f"  const [n] = await {c.Res}.update({{ {field}: req.body.{field} }}, {{ where: {{ id: req.params.{c.idv}, {c.owner}: req.user.id }} }});\n  res.sendStatus(n ? 204 : 404);\n",
        )
        p = js_route(
            c,
            "PATCH",
            path,
            f"  if (!req.user) return res.sendStatus(401);\n  await {c.Res}.update({{ {field}: req.body.{field} }}, {{ where: {{ id: req.params.{c.idv} }} }});\n  res.sendStatus(204);\n",
        )
    else:
        v = py_route(
            c,
            "PATCH",
            path,
            f"{c.idv}: int, body: {c.Res}Update",
            f'    {c.db}.query({c.Res}).filter({c.Res}.id == {c.idv}).update({{"{field}": body.{field}}})\n    {c.db}.commit()\n',
        )
        f = py_route(
            c,
            "PATCH",
            path,
            f"{c.idv}: int, body: {c.Res}Update",
            f'    n = {c.db}.query({c.Res}).filter({c.Res}.id == {c.idv}, {c.Res}.{c.owner} == {c.user}.id).update({{"{field}": body.{field}}})\n    if not n:\n        raise NotFound()\n    {c.db}.commit()\n',
        )
        p = py_route(
            c,
            "PATCH",
            path,
            f"{c.idv}: int, body: {c.Res}Update",
            f'    if {c.user} is None:\n        raise Unauthorized()\n    {c.db}.query({c.Res}).filter({c.Res}.id == {c.idv}).update({{"{field}": body.{field}}})\n    {c.db}.commit()\n',
        )
    return Sample(
        "idor_update",
        "CWE-639",
        c.fw,
        v,
        f,
        p,
        "missing_check",
        "add_ownership_predicate",
        "WSTG-ATHZ-04",
        f"user B modified user A's {c.res}",
    )


# ----------------------------------------------------------------- CWE-862 missing authorization


@family("CWE-862")
def admin_no_role(c: Ctx) -> Sample:
    action = c.pick("delete_user", "purge_cache", "export_all", "reset_billing")
    path = f"/admin/{action.replace('_', '-')}"
    if c.fw == "express":
        v = js_route(
            c, "POST", path, f"  await admin.{action}(req.body.target);\n  res.sendStatus(204);\n"
        )
        f = js_route(
            c,
            "POST",
            path,
            f"  if (!req.user.roles.includes('admin')) return res.sendStatus(403);\n  await admin.{action}(req.body.target);\n  res.sendStatus(204);\n",
        )
        p = js_route(
            c,
            "POST",
            path,
            f"  if (!req.user) return res.sendStatus(403);\n  await admin.{action}(req.body.target);\n  res.sendStatus(204);\n",
        )
    else:
        v = py_route(
            c,
            "POST",
            path,
            "body: AdminAction",
            f'    admin.{action}(body.target)\n    return {{"ok": True}}\n',
        )
        f = py_route(
            c,
            "POST",
            path,
            "body: AdminAction",
            f'    if "admin" not in {c.user}.roles:\n        raise Forbidden()\n    admin.{action}(body.target)\n    return {{"ok": True}}\n',
        )
        p = py_route(
            c,
            "POST",
            path,
            "body: AdminAction",
            f'    if not {c.user}.is_active:\n        raise Forbidden()\n    admin.{action}(body.target)\n    return {{"ok": True}}\n',
        )
    return Sample(
        "admin_no_role",
        "CWE-862",
        c.fw,
        v,
        f,
        p,
        "missing_check",
        "enforce_role_check",
        "WSTG-ATHZ-02",
        f"a non-admin identity invoked {path} (204)",
    )


@family("CWE-862")
def unauth_route(c: Ctx) -> Sample:
    path = f"/{c.res}s/export"
    if c.fw == "express":
        v = js_route(c, "GET", path, f"  res.json(await {c.Res}.findAll());\n", auth=False)
        f = js_route(
            c,
            "GET",
            path,
            f"  res.json(await {c.Res}.findAll({{ where: {{ {c.owner}: req.user.id }} }}));\n",
        )
        p = js_route(
            c,
            "GET",
            path,
            f"  if (req.headers['x-internal']) return res.json(await {c.Res}.findAll());\n  res.sendStatus(401);\n",
            auth=False,
        )
    else:
        v = py_route(c, "GET", path, "", f"    return {c.db}.query({c.Res}).all()\n", auth=False)
        f = py_route(
            c,
            "GET",
            path,
            "",
            f"    return {c.db}.query({c.Res}).filter({c.Res}.{c.owner} == {c.user}.id).all()\n",
        )
        p = py_route(
            c,
            "GET",
            path,
            "request: Request",
            '    if request.headers.get("x-internal"):\n'
            + f"        return {c.db}.query({c.Res}).all()\n    raise Unauthorized()\n",
            auth=False,
        )
    return Sample(
        "unauth_route",
        "CWE-862",
        c.fw,
        v,
        f,
        p,
        "missing_check",
        "require_authentication",
        "WSTG-ATHZ-02",
        f"anonymous request listed every {c.res}",
    )


@family("CWE-862")
def role_from_client(c: Ctx) -> Sample:
    path = f"/{c.res}s/{{{c.idv}}}/approve"
    if c.fw == "express":
        v = js_route(
            c,
            "POST",
            path,
            f"  if (req.body.role !== 'manager') return res.sendStatus(403);\n  await {c.Res}.approve(req.params.{c.idv});\n  res.sendStatus(204);\n",
        )
        f = js_route(
            c,
            "POST",
            path,
            f"  if (!req.user.roles.includes('manager')) return res.sendStatus(403);\n  await {c.Res}.approve(req.params.{c.idv});\n  res.sendStatus(204);\n",
        )
        p = js_route(
            c,
            "POST",
            path,
            f"  if (req.body.role !== 'manager' && !req.user.roles.includes('manager')) return res.sendStatus(403);\n  await {c.Res}.approve(req.params.{c.idv});\n  res.sendStatus(204);\n",
        )
    else:
        v = py_route(
            c,
            "POST",
            path,
            f"{c.idv}: int, body: Approval",
            f'    if body.role != "manager":\n        raise Forbidden()\n    approve_{c.res}({c.idv})\n',
        )
        f = py_route(
            c,
            "POST",
            path,
            f"{c.idv}: int, body: Approval",
            f'    if "manager" not in {c.user}.roles:\n        raise Forbidden()\n    approve_{c.res}({c.idv})\n',
        )
        p = py_route(
            c,
            "POST",
            path,
            f"{c.idv}: int, body: Approval",
            f'    if body.role != "manager" and "manager" not in {c.user}.roles:\n        raise Forbidden()\n    approve_{c.res}({c.idv})\n',
        )
    return Sample(
        "role_from_client",
        "CWE-862",
        c.fw,
        v,
        f,
        p,
        "wrong_check",
        "enforce_role_check",
        "WSTG-ATHZ-02",
        "request with a forged role field was accepted",
    )


@family("CWE-862")
def delete_no_check(c: Ctx) -> Sample:
    path = f"/{c.res}s/{{{c.idv}}}"
    if c.fw == "express":
        v = js_route(
            c,
            "DELETE",
            path,
            f"  await {c.Res}.destroy({{ where: {{ id: req.params.{c.idv} }} }});\n  res.sendStatus(204);\n",
        )
        f = js_route(
            c,
            "DELETE",
            path,
            f"  if (!can(req.user, 'delete', '{c.res}')) return res.sendStatus(403);\n  await {c.Res}.destroy({{ where: {{ id: req.params.{c.idv}, {c.owner}: req.user.id }} }});\n  res.sendStatus(204);\n",
        )
        p = js_route(
            c,
            "DELETE",
            path,
            f"  can(req.user, 'delete', '{c.res}');\n  await {c.Res}.destroy({{ where: {{ id: req.params.{c.idv} }} }});\n  res.sendStatus(204);\n",
        )
    else:
        v = py_route(
            c,
            "DELETE",
            path,
            f"{c.idv}: int",
            f"    {c.db}.query({c.Res}).filter({c.Res}.id == {c.idv}).delete()\n    {c.db}.commit()\n",
        )
        f = py_route(
            c,
            "DELETE",
            path,
            f"{c.idv}: int",
            f'    if not policy.can({c.user}, "delete", "{c.res}"):\n        raise Forbidden()\n    {c.db}.query({c.Res}).filter({c.Res}.id == {c.idv}).delete()\n    {c.db}.commit()\n',
        )
        p = py_route(
            c,
            "DELETE",
            path,
            f"{c.idv}: int",
            f'    policy.can({c.user}, "delete", "{c.res}")\n    {c.db}.query({c.Res}).filter({c.Res}.id == {c.idv}).delete()\n    {c.db}.commit()\n',
        )
    return Sample(
        "delete_no_check",
        "CWE-862",
        c.fw,
        v,
        f,
        p,
        "missing_check",
        "enforce_role_check",
        "WSTG-ATHZ-02",
        f"a read-only identity deleted a {c.res}",
    )


# ----------------------------------------------------------------- CWE-89 SQL injection


@family("CWE-89")
def sqli_fstring(c: Ctx) -> Sample:
    col = c.pick("name", "email", "title", "status")
    path = f"/{c.res}s/search"
    if c.fw == "express":
        v = js_route(
            c,
            "GET",
            path,
            f"  const {{ rows }} = await pool.query(`SELECT * FROM {c.table} WHERE {col} = '${{req.query.q}}'`);\n  res.json(rows);\n",
        )
        f = js_route(
            c,
            "GET",
            path,
            f"  const {{ rows }} = await pool.query('SELECT * FROM {c.table} WHERE {col} = $1', [req.query.q]);\n  res.json(rows);\n",
        )
        p = js_route(
            c,
            "GET",
            path,
            f"  const q = req.query.q.replace(/'/g, '');\n  const {{ rows }} = await pool.query(`SELECT * FROM {c.table} WHERE {col} = '${{q}}'`);\n  res.json(rows);\n",
        )
    else:
        v = py_route(
            c,
            "GET",
            path,
            "q: str",
            f"    return {c.db}.execute(f\"SELECT * FROM {c.table} WHERE {col} = '{{q}}'\").fetchall()\n",
        )
        f = py_route(
            c,
            "GET",
            path,
            "q: str",
            f'    return {c.db}.execute("SELECT * FROM {c.table} WHERE {col} = ?", (q,)).fetchall()\n',
        )
        p = py_route(
            c,
            "GET",
            path,
            "q: str",
            f'    q = q.replace("\'", "")\n    return {c.db}.execute(f"SELECT * FROM {c.table} WHERE {col} = \'{{q}}\'").fetchall()\n',
        )
    return Sample(
        "sqli_fstring",
        "CWE-89",
        c.fw,
        v,
        f,
        p,
        "missing_check",
        "parameterize_query",
        "WSTG-INPV-05",
        "a quote in q changed the query result (boolean-based difference)",
    )


@family("CWE-89")
def sqli_concat(c: Ctx) -> Sample:
    path = f"/{c.res}s"
    sort = c.pick("sort", "order_by", "orderBy")
    if c.fw == "express":
        v = js_route(
            c,
            "GET",
            path,
            f"  const sql = 'SELECT * FROM {c.table} ORDER BY ' + req.query.{sort};\n  res.json((await pool.query(sql)).rows);\n",
        )
        f = js_route(
            c,
            "GET",
            path,
            f"  const col = ['created_at', 'name'].includes(req.query.{sort}) ? req.query.{sort} : 'created_at';\n  const sql = 'SELECT * FROM {c.table} ORDER BY ' + col;\n  res.json((await pool.query(sql)).rows);\n",
        )
        p = js_route(
            c,
            "GET",
            path,
            f"  const col = req.query.{sort}.split(' ')[0];\n  const sql = 'SELECT * FROM {c.table} ORDER BY ' + col;\n  res.json((await pool.query(sql)).rows);\n",
        )
    else:
        v = py_route(
            c,
            "GET",
            path,
            f'{sort}: str = "created_at"',
            f'    sql = "SELECT * FROM {c.table} ORDER BY " + {sort}\n    return {c.db}.execute(sql).fetchall()\n',
        )
        f = py_route(
            c,
            "GET",
            path,
            f'{sort}: str = "created_at"',
            f'    col = {sort} if {sort} in {{"created_at", "name"}} else "created_at"\n    sql = "SELECT * FROM {c.table} ORDER BY " + col\n    return {c.db}.execute(sql).fetchall()\n',
        )
        p = py_route(
            c,
            "GET",
            path,
            f'{sort}: str = "created_at"',
            f'    col = {sort}.split()[0]\n    sql = "SELECT * FROM {c.table} ORDER BY " + col\n    return {c.db}.execute(sql).fetchall()\n',
        )
    return Sample(
        "sqli_concat",
        "CWE-89",
        c.fw,
        v,
        f,
        p,
        "missing_check",
        "allowlist_identifier",
        "WSTG-INPV-05",
        "ORDER BY input altered query execution",
    )


@family("CWE-89")
def sqli_format(c: Ctx) -> Sample:
    path = f"/{c.res}s/by-tag"
    if c.fw == "express":
        v = js_route(
            c,
            "GET",
            path,
            f"  const sql = util.format(\"SELECT id FROM {c.table} WHERE tag = '%s'\", req.query.tag);\n  res.json((await pool.query(sql)).rows);\n",
        )
        f = js_route(
            c,
            "GET",
            path,
            f"  res.json((await pool.query('SELECT id FROM {c.table} WHERE tag = $1', [req.query.tag])).rows);\n",
        )
        p = js_route(
            c,
            "GET",
            path,
            f"  const sql = util.format(\"SELECT id FROM {c.table} WHERE tag = '%s'\", escape(req.query.tag).slice(0, 20));\n  res.json((await pool.query(sql)).rows);\n",
        )
    else:
        v = py_route(
            c,
            "GET",
            path,
            "tag: str",
            f"    cursor.execute(\"SELECT id FROM {c.table} WHERE tag = '%s'\" % tag)\n    return cursor.fetchall()\n",
        )
        f = py_route(
            c,
            "GET",
            path,
            "tag: str",
            f'    cursor.execute("SELECT id FROM {c.table} WHERE tag = %s", (tag,))\n    return cursor.fetchall()\n',
        )
        p = py_route(
            c,
            "GET",
            path,
            "tag: str",
            f"    cursor.execute(\"SELECT id FROM {c.table} WHERE tag = '%s'\" % tag[:20])\n    return cursor.fetchall()\n",
        )
    return Sample(
        "sqli_format",
        "CWE-89",
        c.fw,
        v,
        f,
        p,
        "missing_check",
        "parameterize_query",
        "WSTG-INPV-05",
        "time-based payload in tag delayed the response",
    )


@family("CWE-89")
def sqli_raw_orm(c: Ctx) -> Sample:
    path = f"/{c.res}s/lookup"
    if c.fw == "express":
        v = js_route(
            c,
            "GET",
            path,
            f"  res.json(await sequelize.query(`SELECT * FROM {c.table} WHERE ref = '${{req.query.ref}}'`));\n",
        )
        f = js_route(
            c,
            "GET",
            path,
            f"  res.json(await sequelize.query('SELECT * FROM {c.table} WHERE ref = :ref', {{ replacements: {{ ref: req.query.ref }} }}));\n",
        )
        p = js_route(
            c,
            "GET",
            path,
            f"  if (/;/.test(req.query.ref)) return res.sendStatus(400);\n  res.json(await sequelize.query(`SELECT * FROM {c.table} WHERE ref = '${{req.query.ref}}'`));\n",
        )
    else:
        v = py_route(
            c,
            "GET",
            path,
            "ref: str",
            f'    return {c.db}.execute(text("SELECT * FROM {c.table} WHERE ref = \'" + ref + "\'")).all()\n',
        )
        f = py_route(
            c,
            "GET",
            path,
            "ref: str",
            f'    return {c.db}.execute(text("SELECT * FROM {c.table} WHERE ref = :ref"), {{"ref": ref}}).all()\n',
        )
        p = py_route(
            c,
            "GET",
            path,
            "ref: str",
            f'    if ";" in ref:\n        raise BadRequest()\n    return {c.db}.execute(text("SELECT * FROM {c.table} WHERE ref = \'" + ref + "\'")).all()\n',
        )
    return Sample(
        "sqli_raw_orm",
        "CWE-89",
        c.fw,
        v,
        f,
        p,
        "missing_check",
        "parameterize_query",
        "WSTG-INPV-05",
        "UNION payload in ref returned extra columns",
    )


# ----------------------------------------------------------------- CWE-78 command injection


@family("CWE-78")
def cmd_shell_true(c: Ctx) -> Sample:
    tool = c.pick("convert", "ffmpeg", "pdftotext", "zip")
    path = f"/{c.res}s/convert"
    if c.fw == "express":
        v = js_route(
            c,
            "POST",
            path,
            f"  exec(`{tool} ${{req.body.filename}} out.bin`, (err) => res.sendStatus(err ? 500 : 204));\n",
        )
        f = js_route(
            c,
            "POST",
            path,
            f"  execFile('{tool}', [req.body.filename, 'out.bin'], (err) => res.sendStatus(err ? 500 : 204));\n",
        )
        p = js_route(
            c,
            "POST",
            path,
            f"  const name = req.body.filename.replace(';', '');\n  exec(`{tool} ${{name}} out.bin`, (err) => res.sendStatus(err ? 500 : 204));\n",
        )
    else:
        v = py_route(
            c,
            "POST",
            path,
            "body: ConvertRequest",
            f'    subprocess.run(f"{tool} {{body.filename}} out.bin", shell=True, check=True)\n',
        )
        f = py_route(
            c,
            "POST",
            path,
            "body: ConvertRequest",
            f'    subprocess.run(["{tool}", body.filename, "out.bin"], check=True)\n',
        )
        p = py_route(
            c,
            "POST",
            path,
            "body: ConvertRequest",
            f'    name = body.filename.replace(";", "")\n    subprocess.run(f"{tool} {{name}} out.bin", shell=True, check=True)\n',
        )
    return Sample(
        "cmd_shell_true",
        "CWE-78",
        c.fw,
        v,
        f,
        p,
        "missing_check",
        "use_argument_list",
        "WSTG-INPV-12",
        "a filename containing $(sleep 5) delayed the response",
    )


@family("CWE-78")
def cmd_os_system(c: Ctx) -> Sample:
    path = "/tools/ping"
    if c.fw == "express":
        v = js_route(
            c, "GET", path, "  exec('ping -c 1 ' + req.query.host, (e, out) => res.send(out));\n"
        )
        f = js_route(
            c,
            "GET",
            path,
            "  if (!isIP(req.query.host)) return res.sendStatus(400);\n  execFile('ping', ['-c', '1', req.query.host], (e, out) => res.send(out));\n",
        )
        p = js_route(
            c,
            "GET",
            path,
            "  if (req.query.host.includes('&')) return res.sendStatus(400);\n  exec('ping -c 1 ' + req.query.host, (e, out) => res.send(out));\n",
        )
    else:
        v = py_route(c, "GET", path, "host: str", '    os.system("ping -c 1 " + host)\n')
        f = py_route(
            c,
            "GET",
            path,
            "host: str",
            '    ipaddress.ip_address(host)\n    subprocess.run(["ping", "-c", "1", host], check=False)\n',
        )
        p = py_route(
            c,
            "GET",
            path,
            "host: str",
            '    if "&" in host:\n        raise BadRequest()\n    os.system("ping -c 1 " + host)\n',
        )
    return Sample(
        "cmd_os_system",
        "CWE-78",
        c.fw,
        v,
        f,
        p,
        "missing_check",
        "validate_and_use_argument_list",
        "WSTG-INPV-12",
        "host=127.0.0.1;id returned uid output",
    )


@family("CWE-78")
def cmd_popen(c: Ctx) -> Sample:
    path = f"/{c.res}s/archive"
    if c.fw == "express":
        v = js_route(
            c,
            "POST",
            path,
            "  const out = execSync('tar czf /tmp/a.tgz ' + req.body.dir);\n  res.send(out);\n",
        )
        f = js_route(
            c,
            "POST",
            path,
            "  const dir = path.join(BASE, path.basename(req.body.dir));\n  const out = execFileSync('tar', ['czf', '/tmp/a.tgz', dir]);\n  res.send(out);\n",
        )
        p = js_route(
            c,
            "POST",
            path,
            "  const out = execSync('tar czf /tmp/a.tgz \"' + req.body.dir + '\"');\n  res.send(out);\n",
        )
    else:
        v = py_route(
            c,
            "POST",
            path,
            "body: ArchiveRequest",
            '    out = os.popen("tar czf /tmp/a.tgz " + body.dir).read()\n    return {"out": out}\n',
        )
        f = py_route(
            c,
            "POST",
            path,
            "body: ArchiveRequest",
            '    target = safe_join(BASE, body.dir)\n    out = subprocess.run(["tar", "czf", "/tmp/a.tgz", target], capture_output=True).stdout\n    return {"out": out}\n',
        )
        p = py_route(
            c,
            "POST",
            path,
            "body: ArchiveRequest",
            "    out = os.popen('tar czf /tmp/a.tgz \"' + body.dir + '\"').read()\n    return {\"out\": out}\n",
        )
    return Sample(
        "cmd_popen",
        "CWE-78",
        c.fw,
        v,
        f,
        p,
        "missing_check",
        "use_argument_list",
        "WSTG-INPV-12",
        "dir containing a backtick executed a command",
    )


@family("CWE-78")
def cmd_template_tool(c: Ctx) -> Sample:
    path = "/reports/render"
    if c.fw == "express":
        v = js_route(
            c,
            "POST",
            path,
            "  spawn('sh', ['-c', `wkhtmltopdf ${req.body.url} out.pdf`]).on('close', () => res.sendStatus(204));\n",
        )
        f = js_route(
            c,
            "POST",
            path,
            "  spawn('wkhtmltopdf', [new URL(req.body.url).href, 'out.pdf']).on('close', () => res.sendStatus(204));\n",
        )
        p = js_route(
            c,
            "POST",
            path,
            "  spawn('sh', ['-c', `wkhtmltopdf '${req.body.url}' out.pdf`]).on('close', () => res.sendStatus(204));\n",
        )
    else:
        v = py_route(
            c,
            "POST",
            path,
            "body: RenderRequest",
            '    subprocess.check_call(["sh", "-c", "wkhtmltopdf %s out.pdf" % body.url])\n',
        )
        f = py_route(
            c,
            "POST",
            path,
            "body: RenderRequest",
            '    subprocess.check_call(["wkhtmltopdf", validate_url(body.url), "out.pdf"])\n',
        )
        p = py_route(
            c,
            "POST",
            path,
            "body: RenderRequest",
            '    subprocess.check_call(["sh", "-c", "wkhtmltopdf \'%s\' out.pdf" % body.url])\n',
        )
    return Sample(
        "cmd_template_tool",
        "CWE-78",
        c.fw,
        v,
        f,
        p,
        "missing_check",
        "use_argument_list",
        "WSTG-INPV-12",
        "url with a closing quote ran a second command",
    )


# ----------------------------------------------------------------- CWE-22 path traversal


@family("CWE-22")
def path_join(c: Ctx) -> Sample:
    path = "/files/{name}"
    if c.fw == "express":
        v = js_route(c, "GET", path, "  res.sendFile(path.join(UPLOADS, req.params.name));\n")
        f = js_route(
            c,
            "GET",
            path,
            "  const p = path.resolve(UPLOADS, req.params.name);\n  if (!p.startsWith(UPLOADS + path.sep)) return res.sendStatus(400);\n  res.sendFile(p);\n",
        )
        p = js_route(
            c,
            "GET",
            path,
            "  res.sendFile(path.join(UPLOADS, req.params.name.replace('../', '')));\n",
        )
    else:
        v = py_route(
            c, "GET", path, "name: str", "    return FileResponse(os.path.join(UPLOAD_DIR, name))\n"
        )
        f = py_route(
            c,
            "GET",
            path,
            "name: str",
            "    full = (UPLOAD_DIR / name).resolve()\n    if not full.is_relative_to(UPLOAD_DIR):\n        raise BadRequest()\n    return FileResponse(full)\n",
        )
        p = py_route(
            c,
            "GET",
            path,
            "name: str",
            '    return FileResponse(os.path.join(UPLOAD_DIR, name.replace("../", "")))\n',
        )
    return Sample(
        "path_join",
        "CWE-22",
        c.fw,
        v,
        f,
        p,
        "missing_check",
        "canonicalize_and_contain_path",
        "WSTG-ATHZ-01",
        "name=..%2f..%2fetc%2fpasswd returned a system file",
    )


@family("CWE-22")
def path_open(c: Ctx) -> Sample:
    path = f"/{c.res}s/attachment"
    if c.fw == "express":
        v = js_route(c, "GET", path, "  res.send(fs.readFileSync(`${BASE}/${req.query.file}`));\n")
        f = js_route(
            c,
            "GET",
            path,
            "  const file = path.basename(req.query.file);\n  res.send(fs.readFileSync(path.join(BASE, file)));\n",
        )
        p = js_route(
            c,
            "GET",
            path,
            "  if (req.query.file.startsWith('/')) return res.sendStatus(400);\n  res.send(fs.readFileSync(`${BASE}/${req.query.file}`));\n",
        )
    else:
        v = py_route(
            c,
            "GET",
            path,
            "file: str",
            '    with open(f"{BASE}/{file}", "rb") as fh:\n        return Response(fh.read())\n',
        )
        f = py_route(
            c,
            "GET",
            path,
            "file: str",
            '    safe = os.path.basename(file)\n    with open(os.path.join(BASE, safe), "rb") as fh:\n        return Response(fh.read())\n',
        )
        p = py_route(
            c,
            "GET",
            path,
            "file: str",
            '    if file.startswith("/"):\n        raise BadRequest()\n    with open(f"{BASE}/{file}", "rb") as fh:\n        return Response(fh.read())\n',
        )
    return Sample(
        "path_open",
        "CWE-22",
        c.fw,
        v,
        f,
        p,
        "missing_check",
        "canonicalize_and_contain_path",
        "WSTG-ATHZ-01",
        "file=../../app/settings.py returned source",
    )


@family("CWE-22")
def path_extract(c: Ctx) -> Sample:
    path = "/imports"
    if c.fw == "express":
        v = js_route(
            c,
            "POST",
            path,
            "  for (const e of zip.getEntries()) fs.writeFileSync(path.join(DEST, e.entryName), e.getData());\n  res.sendStatus(204);\n",
        )
        f = js_route(
            c,
            "POST",
            path,
            "  for (const e of zip.getEntries()) {\n    const out = path.resolve(DEST, e.entryName);\n    if (!out.startsWith(DEST + path.sep)) continue;\n    fs.writeFileSync(out, e.getData());\n  }\n  res.sendStatus(204);\n",
        )
        p = js_route(
            c,
            "POST",
            path,
            "  for (const e of zip.getEntries()) if (!e.entryName.startsWith('/')) fs.writeFileSync(path.join(DEST, e.entryName), e.getData());\n  res.sendStatus(204);\n",
        )
    else:
        v = py_route(
            c,
            "POST",
            path,
            "upload: UploadFile",
            "    with zipfile.ZipFile(upload.file) as z:\n        z.extractall(DEST)\n",
        )
        f = py_route(
            c,
            "POST",
            path,
            "upload: UploadFile",
            "    with zipfile.ZipFile(upload.file) as z:\n        for m in z.namelist():\n            if not (DEST / m).resolve().is_relative_to(DEST):\n                raise BadRequest()\n        z.extractall(DEST)\n",
        )
        p = py_route(
            c,
            "POST",
            path,
            "upload: UploadFile",
            '    with zipfile.ZipFile(upload.file) as z:\n        for m in z.namelist():\n            if m.startswith("/"):\n                raise BadRequest()\n        z.extractall(DEST)\n',
        )
    return Sample(
        "path_extract",
        "CWE-22",
        c.fw,
        v,
        f,
        p,
        "missing_check",
        "canonicalize_and_contain_path",
        "WSTG-ATHZ-01",
        "an archive entry ../../x wrote outside the import directory",
    )


@family("CWE-22")
def path_template(c: Ctx) -> Sample:
    path = "/theme"
    if c.fw == "express":
        v = js_route(c, "GET", path, "  res.render('themes/' + req.query.name);\n")
        f = js_route(
            c,
            "GET",
            path,
            "  const name = THEMES.includes(req.query.name) ? req.query.name : 'default';\n  res.render('themes/' + name);\n",
        )
        p = js_route(
            c, "GET", path, "  res.render('themes/' + req.query.name.replace(/\\.\\./, ''));\n"
        )
    else:
        v = py_route(
            c,
            "GET",
            path,
            "name: str",
            '    return templates.TemplateResponse("themes/" + name, {})\n',
        )
        f = py_route(
            c,
            "GET",
            path,
            "name: str",
            '    name = name if name in THEMES else "default.html"\n    return templates.TemplateResponse("themes/" + name, {})\n',
        )
        p = py_route(
            c,
            "GET",
            path,
            "name: str",
            '    return templates.TemplateResponse("themes/" + name.replace("..", "", 1), {})\n',
        )
    return Sample(
        "path_template",
        "CWE-22",
        c.fw,
        v,
        f,
        p,
        "missing_check",
        "allowlist_identifier",
        "WSTG-ATHZ-01",
        "name=../../admin.html rendered a template outside themes/",
    )


# ----------------------------------------------------------------- CWE-79 XSS


@family("CWE-79")
def xss_fstring_html(c: Ctx) -> Sample:
    path = "/greet"
    if c.fw == "express":
        v = js_route(
            c, "GET", path, "  res.send(`<h1>Hello ${req.query.name}</h1>`);\n", auth=False
        )
        f = js_route(
            c,
            "GET",
            path,
            "  res.send(`<h1>Hello ${escapeHtml(req.query.name)}</h1>`);\n",
            auth=False,
        )
        p = js_route(
            c,
            "GET",
            path,
            "  res.send(`<h1>Hello ${req.query.name.replace('<script>', '')}</h1>`);\n",
            auth=False,
        )
    else:
        v = py_route(
            c,
            "GET",
            path,
            "name: str",
            '    return HTMLResponse(f"<h1>Hello {name}</h1>")\n',
            auth=False,
        )
        f = py_route(
            c,
            "GET",
            path,
            "name: str",
            '    return HTMLResponse(f"<h1>Hello {html.escape(name)}</h1>")\n',
            auth=False,
        )
        p = py_route(
            c,
            "GET",
            path,
            "name: str",
            "    return HTMLResponse(f\"<h1>Hello {name.replace('<script>', '')}</h1>\")\n",
            auth=False,
        )
    return Sample(
        "xss_fstring_html",
        "CWE-79",
        c.fw,
        v,
        f,
        p,
        "missing_check",
        "encode_output",
        "WSTG-INPV-01",
        "name=<img src=x onerror=alert(1)> was reflected unencoded",
    )


@family("CWE-79")
def xss_markup_safe(c: Ctx) -> Sample:
    path = f"/{c.res}s/{{{c.idv}}}/preview"
    if c.fw == "express":
        v = js_route(
            c,
            "GET",
            path,
            f"  const {c.var} = await {c.Res}.findByPk(req.params.{c.idv});\n  res.render('preview', {{ body: {c.var}.body, unescaped: true }});\n",
        )
        f = js_route(
            c,
            "GET",
            path,
            f"  const {c.var} = await {c.Res}.findByPk(req.params.{c.idv});\n  res.render('preview', {{ body: sanitizeHtml({c.var}.body) }});\n",
        )
        p = js_route(
            c,
            "GET",
            path,
            f"  const {c.var} = await {c.Res}.findByPk(req.params.{c.idv});\n  res.render('preview', {{ body: {c.var}.body.replace(/script/gi, ''), unescaped: true }});\n",
        )
    else:
        v = py_route(
            c,
            "GET",
            path,
            f"{c.idv}: int",
            f'    {c.var} = {c.db}.get({c.Res}, {c.idv})\n    return render_template("preview.html", body=Markup({c.var}.body))\n',
        )
        f = py_route(
            c,
            "GET",
            path,
            f"{c.idv}: int",
            f'    {c.var} = {c.db}.get({c.Res}, {c.idv})\n    return render_template("preview.html", body=bleach.clean({c.var}.body))\n',
        )
        p = py_route(
            c,
            "GET",
            path,
            f"{c.idv}: int",
            f'    {c.var} = {c.db}.get({c.Res}, {c.idv})\n    return render_template("preview.html", body=Markup({c.var}.body.replace("script", "")))\n',
        )
    return Sample(
        "xss_markup_safe",
        "CWE-79",
        c.fw,
        v,
        f,
        p,
        "unsafe_default",
        "sanitize_rich_text",
        "WSTG-INPV-02",
        "stored body with an event handler executed in the preview",
    )


@family("CWE-79")
def xss_innerhtml(c: Ctx) -> Sample:
    path = "/search"
    if c.fw == "express":
        v = js_route(
            c,
            "GET",
            path,
            "  res.send(`<script>document.getElementById('q').innerHTML = '${req.query.q}';</script>`);\n",
            auth=False,
        )
        f = js_route(
            c,
            "GET",
            path,
            "  res.send(`<script>document.getElementById('q').textContent = ${JSON.stringify(String(req.query.q))};</script>`);\n",
            auth=False,
        )
        p = js_route(
            c,
            "GET",
            path,
            "  res.send(`<script>document.getElementById('q').innerHTML = '${req.query.q.replace(/'/g, '')}';</script>`);\n",
            auth=False,
        )
    else:
        v = py_route(
            c,
            "GET",
            path,
            "q: str",
            '    return HTMLResponse("<script>el.innerHTML = \'" + q + "\';</script>")\n',
            auth=False,
        )
        f = py_route(
            c,
            "GET",
            path,
            "q: str",
            '    return HTMLResponse("<script>el.textContent = " + json.dumps(q) + ";</script>")\n',
            auth=False,
        )
        p = py_route(
            c,
            "GET",
            path,
            "q: str",
            '    return HTMLResponse("<script>el.innerHTML = \'" + q.replace("\'", "") + "\';</script>")\n',
            auth=False,
        )
    return Sample(
        "xss_innerhtml",
        "CWE-79",
        c.fw,
        v,
        f,
        p,
        "missing_check",
        "encode_output",
        "WSTG-INPV-01",
        "q broke out of the script string context",
    )


@family("CWE-79")
def xss_autoescape_off(c: Ctx) -> Sample:
    path = "/profile/bio"
    if c.fw == "express":
        v = js_route(
            c,
            "GET",
            path,
            "  const env = nunjucks.configure('views', { autoescape: false });\n  res.send(env.render('bio.html', { bio: req.user.bio }));\n",
        )
        f = js_route(
            c,
            "GET",
            path,
            "  const env = nunjucks.configure('views', { autoescape: true });\n  res.send(env.render('bio.html', { bio: req.user.bio }));\n",
        )
        p = js_route(
            c,
            "GET",
            path,
            "  const env = nunjucks.configure('views', { autoescape: false });\n  res.send(env.render('bio.html', { bio: req.user.bio.slice(0, 200) }));\n",
        )
    else:
        v = py_route(
            c,
            "GET",
            path,
            "",
            f'    env = Environment(loader=loader, autoescape=False)\n    return HTMLResponse(env.get_template("bio.html").render(bio={c.user}.bio))\n',
        )
        f = py_route(
            c,
            "GET",
            path,
            "",
            f'    env = Environment(loader=loader, autoescape=True)\n    return HTMLResponse(env.get_template("bio.html").render(bio={c.user}.bio))\n',
        )
        p = py_route(
            c,
            "GET",
            path,
            "",
            f'    env = Environment(loader=loader, autoescape=False)\n    return HTMLResponse(env.get_template("bio.html").render(bio={c.user}.bio[:200]))\n',
        )
    return Sample(
        "xss_autoescape_off",
        "CWE-79",
        c.fw,
        v,
        f,
        p,
        "unsafe_default",
        "enable_autoescape",
        "WSTG-INPV-02",
        "stored bio markup rendered as HTML",
    )


# ----------------------------------------------------------------- CWE-918 SSRF


@family("CWE-918")
def ssrf_fetch(c: Ctx) -> Sample:
    path = "/webhooks/test"
    if c.fw == "express":
        v = js_route(
            c,
            "POST",
            path,
            "  const r = await fetch(req.body.url);\n  res.json({ status: r.status });\n",
        )
        f = js_route(
            c,
            "POST",
            path,
            "  const u = new URL(req.body.url);\n  if (!ALLOWED_HOSTS.has(u.hostname)) return res.sendStatus(400);\n  const r = await fetch(u, { redirect: 'error' });\n  res.json({ status: r.status });\n",
        )
        p = js_route(
            c,
            "POST",
            path,
            "  if (req.body.url.includes('localhost')) return res.sendStatus(400);\n  const r = await fetch(req.body.url);\n  res.json({ status: r.status });\n",
        )
    else:
        v = py_route(
            c,
            "POST",
            path,
            "body: WebhookTest",
            '    r = httpx.get(body.url, timeout=5)\n    return {"status": r.status_code}\n',
        )
        f = py_route(
            c,
            "POST",
            path,
            "body: WebhookTest",
            '    host = urlparse(body.url).hostname\n    if host not in ALLOWED_HOSTS:\n        raise BadRequest()\n    r = httpx.get(body.url, timeout=5, follow_redirects=False)\n    return {"status": r.status_code}\n',
        )
        p = py_route(
            c,
            "POST",
            path,
            "body: WebhookTest",
            '    if "localhost" in body.url:\n        raise BadRequest()\n    r = httpx.get(body.url, timeout=5)\n    return {"status": r.status_code}\n',
        )
    return Sample(
        "ssrf_fetch",
        "CWE-918",
        c.fw,
        v,
        f,
        p,
        "missing_check",
        "allowlist_outbound_hosts",
        "WSTG-INPV-19",
        "url=http://169.254.169.254/ reached the metadata service",
    )


@family("CWE-918")
def ssrf_image_proxy(c: Ctx) -> Sample:
    path = "/img"
    if c.fw == "express":
        v = js_route(
            c,
            "GET",
            path,
            "  const r = await axios.get(req.query.src, { responseType: 'arraybuffer' });\n  res.type('png').send(r.data);\n",
            auth=False,
        )
        f = js_route(
            c,
            "GET",
            path,
            "  const u = new URL(req.query.src);\n  if (u.protocol !== 'https:' || !CDN_HOSTS.includes(u.host)) return res.sendStatus(400);\n  const r = await axios.get(u.href, { responseType: 'arraybuffer', maxRedirects: 0 });\n  res.type('png').send(r.data);\n",
            auth=False,
        )
        p = js_route(
            c,
            "GET",
            path,
            "  if (!req.query.src.startsWith('http')) return res.sendStatus(400);\n  const r = await axios.get(req.query.src, { responseType: 'arraybuffer' });\n  res.type('png').send(r.data);\n",
            auth=False,
        )
    else:
        v = py_route(
            c,
            "GET",
            path,
            "src: str",
            '    data = requests.get(src).content\n    return Response(data, media_type="image/png")\n',
            auth=False,
        )
        f = py_route(
            c,
            "GET",
            path,
            "src: str",
            '    u = urlparse(src)\n    if u.scheme != "https" or u.hostname not in CDN_HOSTS:\n        raise BadRequest()\n    data = requests.get(src, allow_redirects=False).content\n    return Response(data, media_type="image/png")\n',
            auth=False,
        )
        p = py_route(
            c,
            "GET",
            path,
            "src: str",
            '    if not src.startswith("http"):\n        raise BadRequest()\n    data = requests.get(src).content\n    return Response(data, media_type="image/png")\n',
            auth=False,
        )
    return Sample(
        "ssrf_image_proxy",
        "CWE-918",
        c.fw,
        v,
        f,
        p,
        "missing_check",
        "allowlist_outbound_hosts",
        "WSTG-INPV-19",
        "src pointing at an internal admin port returned its body",
    )


@family("CWE-918")
def ssrf_urlopen(c: Ctx) -> Sample:
    path = f"/{c.res}s/import-url"
    if c.fw == "express":
        v = js_route(c, "POST", path, "  http.get(req.body.feed, (r) => r.pipe(res));\n")
        f = js_route(
            c,
            "POST",
            path,
            "  const u = await resolvePublic(req.body.feed);\n  if (!u) return res.sendStatus(400);\n  https.get(u, (r) => r.pipe(res));\n",
        )
        p = js_route(
            c,
            "POST",
            path,
            "  if (req.body.feed.match(/127\\.0\\.0\\.1/)) return res.sendStatus(400);\n  http.get(req.body.feed, (r) => r.pipe(res));\n",
        )
    else:
        v = py_route(
            c,
            "POST",
            path,
            "body: ImportUrl",
            "    return urllib.request.urlopen(body.feed).read()\n",
        )
        f = py_route(
            c,
            "POST",
            path,
            "body: ImportUrl",
            "    url = resolve_public_url(body.feed)\n    return urllib.request.urlopen(url, timeout=5).read()\n",
        )
        p = py_route(
            c,
            "POST",
            path,
            "body: ImportUrl",
            '    if "127.0.0.1" in body.feed:\n        raise BadRequest()\n    return urllib.request.urlopen(body.feed).read()\n',
        )
    return Sample(
        "ssrf_urlopen",
        "CWE-918",
        c.fw,
        v,
        f,
        p,
        "missing_check",
        "allowlist_outbound_hosts",
        "WSTG-INPV-19",
        "feed=http://[::1]:8080/admin returned internal content",
    )


@family("CWE-918")
def ssrf_pdf(c: Ctx) -> Sample:
    path = "/export/pdf"
    if c.fw == "express":
        v = js_route(
            c,
            "POST",
            path,
            "  const page = await browser.newPage();\n  await page.goto(req.body.target);\n  res.send(await page.pdf());\n",
        )
        f = js_route(
            c,
            "POST",
            path,
            "  const page = await browser.newPage();\n  await page.setRequestInterception(true);\n  page.on('request', (r) => (isPublic(r.url()) ? r.continue() : r.abort()));\n  await page.goto(req.body.target);\n  res.send(await page.pdf());\n",
        )
        p = js_route(
            c,
            "POST",
            path,
            "  const page = await browser.newPage();\n  if (req.body.target.startsWith('file:')) return res.sendStatus(400);\n  await page.goto(req.body.target);\n  res.send(await page.pdf());\n",
        )
    else:
        v = py_route(
            c,
            "POST",
            path,
            "body: ExportPdf",
            '    pdf = pdfkit.from_url(body.target, False)\n    return Response(pdf, media_type="application/pdf")\n',
        )
        f = py_route(
            c,
            "POST",
            path,
            "body: ExportPdf",
            '    if not is_public_url(body.target):\n        raise BadRequest()\n    pdf = pdfkit.from_url(body.target, False, options={"disable-local-file-access": ""})\n    return Response(pdf, media_type="application/pdf")\n',
        )
        p = py_route(
            c,
            "POST",
            path,
            "body: ExportPdf",
            '    if body.target.startswith("file:"):\n        raise BadRequest()\n    pdf = pdfkit.from_url(body.target, False)\n    return Response(pdf, media_type="application/pdf")\n',
        )
    return Sample(
        "ssrf_pdf",
        "CWE-918",
        c.fw,
        v,
        f,
        p,
        "missing_check",
        "allowlist_outbound_hosts",
        "WSTG-INPV-19",
        "the renderer fetched an internal-only URL",
    )


# ----------------------------------------------------------------- CWE-798 hard-coded credentials


def _secret(c: Ctx) -> str:
    return c.pick("sk_live_", "AKIA", "ghp_", "xoxb-", "pk_") + "".join(
        c.rng.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(20)
    )


@family("CWE-798")
def secret_constant(c: Ctx) -> Sample:
    name = c.pick("API_KEY", "STRIPE_SECRET", "AWS_SECRET_ACCESS_KEY", "SLACK_TOKEN")
    s = _secret(c)
    if c.fw == "express":
        v = f"const {name} = '{s}';\n\nmodule.exports = {{ client: new Client({{ key: {name} }}) }};\n"
        f = f"const {name} = process.env.{name};\nif (!{name}) throw new Error('{name} is not set');\n\nmodule.exports = {{ client: new Client({{ key: {name} }}) }};\n"
        p = f"const {name} = process.env.{name} || '{s}';\n\nmodule.exports = {{ client: new Client({{ key: {name} }}) }};\n"
    else:
        v = f'{name} = "{s}"\n\nclient = Client(api_key={name})\n'
        f = f'{name} = os.environ["{name}"]\n\nclient = Client(api_key={name})\n'
        p = f'{name} = os.environ.get("{name}", "{s}")\n\nclient = Client(api_key={name})\n'
    return Sample(
        "secret_constant",
        "CWE-798",
        c.fw,
        v,
        f,
        p,
        "configuration",
        "move_secret_to_environment",
        "WSTG-ATHN-02",
        "a live-looking credential is present in source",
    )


@family("CWE-798")
def secret_db_url(c: Ctx) -> Sample:
    pw = c.pick("hunter2", "Passw0rd!", "admin123", "s3cr3t")
    if c.fw == "express":
        v = f"const pool = new Pool({{ connectionString: 'postgres://app:{pw}@db.internal:5432/{c.res}' }});\n"
        f = "const pool = new Pool({ connectionString: process.env.DATABASE_URL });\n"
        p = f"const pool = new Pool({{ connectionString: process.env.DATABASE_URL || 'postgres://app:{pw}@db.internal:5432/{c.res}' }});\n"
    else:
        v = f'engine = create_engine("postgresql://app:{pw}@db.internal:5432/{c.res}")\n'
        f = 'engine = create_engine(os.environ["DATABASE_URL"])\n'
        p = f'engine = create_engine(os.getenv("DATABASE_URL", "postgresql://app:{pw}@db.internal:5432/{c.res}"))\n'
    return Sample(
        "secret_db_url",
        "CWE-798",
        c.fw,
        v,
        f,
        p,
        "configuration",
        "move_secret_to_environment",
        "WSTG-ATHN-02",
        "database password embedded in a connection string",
    )


@family("CWE-798")
def default_admin(c: Ctx) -> Sample:
    if c.fw == "express":
        v = "async function login(user, pass) {\n  if (user === 'admin' && pass === 'admin') return { role: 'admin' };\n  return db.verify(user, pass);\n}\n"
        f = "async function login(user, pass) {\n  return db.verify(user, pass);\n}\n"
        p = "async function login(user, pass) {\n  if (process.env.NODE_ENV !== 'production' && user === 'admin' && pass === 'admin') return { role: 'admin' };\n  return db.verify(user, pass);\n}\n"
    else:
        v = 'def authenticate(username, password):\n    if username == "admin" and password == "admin":\n        return User(role="admin")\n    return users.verify(username, password)\n'
        f = "def authenticate(username, password):\n    return users.verify(username, password)\n"
        p = 'def authenticate(username, password):\n    if settings.DEBUG and username == "admin" and password == "admin":\n        return User(role="admin")\n    return users.verify(username, password)\n'
    return Sample(
        "default_admin",
        "CWE-798",
        c.fw,
        v,
        f,
        p,
        "unsafe_default",
        "remove_default_credentials",
        "WSTG-ATHN-02",
        "admin/admin authenticated",
    )


@family("CWE-798")
def jwt_secret(c: Ctx) -> Sample:
    k = c.pick("secret", "changeme", "jwt-secret", "dev-key-123")
    if c.fw == "express":
        v = f"const token = jwt.sign({{ sub: user.id }}, '{k}', {{ expiresIn: '1h' }});\n"
        f = "const token = jwt.sign({ sub: user.id }, process.env.JWT_SECRET, { expiresIn: '1h' });\n"
        p = f"const token = jwt.sign({{ sub: user.id }}, process.env.JWT_SECRET ?? '{k}', {{ expiresIn: '1h' }});\n"
    else:
        v = f'token = jwt.encode({{"sub": user.id}}, "{k}", algorithm="HS256")\n'
        f = 'token = jwt.encode({"sub": user.id}, settings.jwt_secret.get_secret_value(), algorithm="HS256")\n'
        p = f'token = jwt.encode({{"sub": user.id}}, os.getenv("JWT_SECRET") or "{k}", algorithm="HS256")\n'
    return Sample(
        "jwt_secret",
        "CWE-798",
        c.fw,
        v,
        f,
        p,
        "configuration",
        "move_secret_to_environment",
        "WSTG-ATHN-02",
        "tokens can be forged with the published signing key",
    )


# ----------------------------------------------------------------- CWE-502 deserialization


@family("CWE-502")
def deser_pickle(c: Ctx) -> Sample:
    path = "/session/restore"
    if c.fw == "express":
        v = js_route(
            c,
            "POST",
            path,
            "  const state = serialize.unserialize(Buffer.from(req.body.blob, 'base64').toString());\n  res.json(state);\n",
        )
        f = js_route(
            c,
            "POST",
            path,
            "  const state = JSON.parse(Buffer.from(req.body.blob, 'base64').toString());\n  res.json(StateSchema.parse(state));\n",
        )
        p = js_route(
            c,
            "POST",
            path,
            "  if (req.body.blob.length > 4096) return res.sendStatus(413);\n  const state = serialize.unserialize(Buffer.from(req.body.blob, 'base64').toString());\n  res.json(state);\n",
        )
    else:
        v = py_route(
            c,
            "POST",
            path,
            "body: Blob",
            "    state = pickle.loads(base64.b64decode(body.data))\n    return state\n",
        )
        f = py_route(
            c,
            "POST",
            path,
            "body: Blob",
            "    state = SessionState.model_validate_json(base64.b64decode(body.data))\n    return state\n",
        )
        p = py_route(
            c,
            "POST",
            path,
            "body: Blob",
            "    if len(body.data) > 4096:\n        raise BadRequest()\n    state = pickle.loads(base64.b64decode(body.data))\n    return state\n",
        )
    return Sample(
        "deser_pickle",
        "CWE-502",
        c.fw,
        v,
        f,
        p,
        "unsafe_default",
        "use_safe_data_format",
        "WSTG-INPV-11",
        "a crafted payload executed code during restore",
    )


@family("CWE-502")
def deser_yaml(c: Ctx) -> Sample:
    path = "/config/import"
    if c.fw == "express":
        v = js_route(
            c,
            "POST",
            path,
            "  const cfg = yaml.load(req.body.text, { schema: yaml.DEFAULT_FULL_SCHEMA });\n  res.json(cfg);\n",
        )
        f = js_route(
            c,
            "POST",
            path,
            "  const cfg = yaml.load(req.body.text, { schema: yaml.CORE_SCHEMA });\n  res.json(cfg);\n",
        )
        p = js_route(
            c,
            "POST",
            path,
            "  if (req.body.text.includes('!!js')) return res.sendStatus(400);\n  const cfg = yaml.load(req.body.text, { schema: yaml.DEFAULT_FULL_SCHEMA });\n  res.json(cfg);\n",
        )
    else:
        v = py_route(
            c,
            "POST",
            path,
            "body: ConfigText",
            "    cfg = yaml.load(body.text, Loader=yaml.Loader)\n    return cfg\n",
        )
        f = py_route(
            c,
            "POST",
            path,
            "body: ConfigText",
            "    cfg = yaml.safe_load(body.text)\n    return cfg\n",
        )
        p = py_route(
            c,
            "POST",
            path,
            "body: ConfigText",
            '    if "!!python" in body.text:\n        raise BadRequest()\n    cfg = yaml.load(body.text, Loader=yaml.Loader)\n    return cfg\n',
        )
    return Sample(
        "deser_yaml",
        "CWE-502",
        c.fw,
        v,
        f,
        p,
        "unsafe_default",
        "use_safe_loader",
        "WSTG-INPV-11",
        "a YAML tag constructed an arbitrary object",
    )


@family("CWE-502")
def deser_cookie(c: Ctx) -> Sample:
    if c.fw == "express":
        v = "app.use((req, res, next) => {\n  req.prefs = serialize.unserialize(req.cookies.prefs || '{}');\n  next();\n});\n"
        f = "app.use((req, res, next) => {\n  req.prefs = JSON.parse(cookieSigner.unsign(req.cookies.prefs) || '{}');\n  next();\n});\n"
        p = "app.use((req, res, next) => {\n  req.prefs = req.cookies.prefs ? serialize.unserialize(req.cookies.prefs) : {};\n  next();\n});\n"
    else:
        v = '@app.before_request\ndef load_prefs():\n    raw = request.cookies.get("prefs")\n    g.prefs = pickle.loads(base64.b64decode(raw)) if raw else {}\n'
        f = '@app.before_request\ndef load_prefs():\n    raw = request.cookies.get("prefs")\n    g.prefs = json.loads(signer.unsign(raw)) if raw else {}\n'
        p = '@app.before_request\ndef load_prefs():\n    raw = request.cookies.get("prefs")\n    g.prefs = pickle.loads(base64.b64decode(raw[:2048])) if raw else {}\n'
    return Sample(
        "deser_cookie",
        "CWE-502",
        c.fw,
        v,
        f,
        p,
        "unsafe_default",
        "use_safe_data_format",
        "WSTG-INPV-11",
        "a forged prefs cookie was deserialized",
    )


@family("CWE-502")
def deser_marshal(c: Ctx) -> Sample:
    path = "/jobs/submit"
    if c.fw == "express":
        v = js_route(
            c,
            "POST",
            path,
            "  const job = eval('(' + req.body.spec + ')');\n  queue.add(job);\n  res.sendStatus(202);\n",
        )
        f = js_route(
            c,
            "POST",
            path,
            "  const job = JobSchema.parse(JSON.parse(req.body.spec));\n  queue.add(job);\n  res.sendStatus(202);\n",
        )
        p = js_route(
            c,
            "POST",
            path,
            "  if (/require|process/.test(req.body.spec)) return res.sendStatus(400);\n  const job = eval('(' + req.body.spec + ')');\n  queue.add(job);\n  res.sendStatus(202);\n",
        )
    else:
        v = py_route(
            c,
            "POST",
            path,
            "body: JobSpec",
            "    job = marshal.loads(bytes.fromhex(body.spec))\n    queue.put(job)\n",
        )
        f = py_route(
            c,
            "POST",
            path,
            "body: JobSpec",
            "    job = Job.model_validate_json(body.spec)\n    queue.put(job)\n",
        )
        p = py_route(
            c,
            "POST",
            path,
            "body: JobSpec",
            "    if len(body.spec) > 10000:\n        raise BadRequest()\n    job = marshal.loads(bytes.fromhex(body.spec))\n    queue.put(job)\n",
        )
    return Sample(
        "deser_marshal",
        "CWE-502",
        c.fw,
        v,
        f,
        p,
        "unsafe_default",
        "use_safe_data_format",
        "WSTG-INPV-11",
        "a submitted job spec was evaluated as code",
    )


# ----------------------------------------------------------------- CWE-916 weak password hash


@family("CWE-916")
def pw_md5(c: Ctx) -> Sample:
    if c.fw == "express":
        v = "function hashPassword(pw) {\n  return crypto.createHash('md5').update(pw).digest('hex');\n}\n"
        f = "async function hashPassword(pw) {\n  return argon2.hash(pw, { type: argon2.argon2id });\n}\n"
        p = "function hashPassword(pw) {\n  return crypto.createHash('sha256').update(SALT + pw).digest('hex');\n}\n"
    else:
        v = "def hash_password(password: str) -> str:\n    return hashlib.md5(password.encode()).hexdigest()\n"
        f = "def hash_password(password: str) -> str:\n    return argon2.PasswordHasher().hash(password)\n"
        p = "def hash_password(password: str) -> str:\n    return hashlib.sha256((SALT + password).encode()).hexdigest()\n"
    return Sample(
        "pw_md5",
        "CWE-916",
        c.fw,
        v,
        f,
        p,
        "wrong_check",
        "use_password_kdf",
        "WSTG-CRYP-04",
        "stored password hashes are fast unsalted digests",
    )


@family("CWE-916")
def pw_sha1_salt(c: Ctx) -> Sample:
    if c.fw == "express":
        v = "user.passwordHash = crypto.createHash('sha1').update(user.salt + req.body.password).digest('hex');\nawait user.save();\n"
        f = "user.passwordHash = await bcrypt.hash(req.body.password, 12);\nawait user.save();\n"
        p = "user.passwordHash = crypto.createHash('sha512').update(user.salt + req.body.password).digest('hex');\nawait user.save();\n"
    else:
        v = "user.password_hash = hashlib.sha1((user.salt + body.password).encode()).hexdigest()\ndb.commit()\n"
        f = "user.password_hash = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt(rounds=12)).decode()\ndb.commit()\n"
        p = "user.password_hash = hashlib.sha512((user.salt + body.password).encode()).hexdigest()\ndb.commit()\n"
    return Sample(
        "pw_sha1_salt",
        "CWE-916",
        c.fw,
        v,
        f,
        p,
        "wrong_check",
        "use_password_kdf",
        "WSTG-CRYP-04",
        "salted SHA-1 password hashes recovered quickly offline",
    )


@family("CWE-916")
def pw_compare(c: Ctx) -> Sample:
    if c.fw == "express":
        v = "async function verify(user, pw) {\n  return user.hash === crypto.createHash('sha256').update(pw).digest('hex');\n}\n"
        f = "async function verify(user, pw) {\n  return argon2.verify(user.hash, pw);\n}\n"
        p = "async function verify(user, pw) {\n  const h = crypto.createHash('sha256').update(pw).digest();\n  return crypto.timingSafeEqual(Buffer.from(user.hash, 'hex'), h);\n}\n"
    else:
        v = "def verify(user, password):\n    return user.hash == hashlib.sha256(password.encode()).hexdigest()\n"
        f = "def verify(user, password):\n    return argon2.PasswordHasher().verify(user.hash, password)\n"
        p = "def verify(user, password):\n    return hmac.compare_digest(user.hash, hashlib.sha256(password.encode()).hexdigest())\n"
    return Sample(
        "pw_compare",
        "CWE-916",
        c.fw,
        v,
        f,
        p,
        "wrong_check",
        "use_password_kdf",
        "WSTG-CRYP-04",
        "passwords verified against unsalted SHA-256",
    )


@family("CWE-916")
def pw_pbkdf_low(c: Ctx) -> Sample:
    n = c.pick("1", "10", "100", "1000")
    if c.fw == "express":
        v = f"const hash = crypto.pbkdf2Sync(pw, salt, {n}, 32, 'sha1').toString('hex');\n"
        f = "const hash = crypto.pbkdf2Sync(pw, salt, 600000, 32, 'sha256').toString('hex');\n"
        p = f"const hash = crypto.pbkdf2Sync(pw, salt, {n}, 64, 'sha512').toString('hex');\n"
    else:
        v = f'digest = hashlib.pbkdf2_hmac("sha1", password.encode(), salt, {n})\n'
        f = 'digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600_000)\n'
        p = f'digest = hashlib.pbkdf2_hmac("sha512", password.encode(), salt, {n})\n'
    return Sample(
        "pw_pbkdf_low",
        "CWE-916",
        c.fw,
        v,
        f,
        p,
        "unsafe_default",
        "raise_kdf_work_factor",
        "WSTG-CRYP-04",
        f"PBKDF2 with {n} iterations",
    )


# ----------------------------------------------------------------- CWE-1284 quantity / bounds


@family("CWE-1284")
def bound_refund(c: Ctx) -> Sample:
    path = f"/{c.res}s/{{{c.idv}}}/refund"
    if c.fw == "express":
        v = js_route(
            c,
            "POST",
            path,
            f"  const p = await Payment.findByPk(req.params.{c.idv});\n  if (req.body.amount > p.amount) return res.sendStatus(400);\n  await p.refund(req.body.amount);\n  res.sendStatus(204);\n",
        )
        f = js_route(
            c,
            "POST",
            path,
            f"  const p = await Payment.findByPk(req.params.{c.idv});\n  if (req.body.amount <= 0 || p.refunded + req.body.amount > p.amount) return res.sendStatus(400);\n  await p.refund(req.body.amount);\n  res.sendStatus(204);\n",
        )
        p = js_route(
            c,
            "POST",
            path,
            f"  const p = await Payment.findByPk(req.params.{c.idv});\n  if (req.body.amount <= 0 || req.body.amount > p.amount) return res.sendStatus(400);\n  await p.refund(req.body.amount);\n  res.sendStatus(204);\n",
        )
    else:
        v = py_route(
            c,
            "POST",
            path,
            f"{c.idv}: int, body: Refund",
            f"    p = {c.db}.get(Payment, {c.idv})\n    if body.amount > p.amount:\n        raise BadRequest()\n    p.refund(body.amount)\n",
        )
        f = py_route(
            c,
            "POST",
            path,
            f"{c.idv}: int, body: Refund",
            f"    p = {c.db}.get(Payment, {c.idv})\n    if body.amount <= 0 or p.refunded + body.amount > p.amount:\n        raise BadRequest()\n    p.refund(body.amount)\n",
        )
        p = py_route(
            c,
            "POST",
            path,
            f"{c.idv}: int, body: Refund",
            f"    p = {c.db}.get(Payment, {c.idv})\n    if body.amount <= 0 or body.amount > p.amount:\n        raise BadRequest()\n    p.refund(body.amount)\n",
        )
    return Sample(
        "bound_refund",
        "CWE-1284",
        c.fw,
        v,
        f,
        p,
        "logic_error",
        "enforce_cumulative_bound",
        "WSTG-BUSL-01",
        "two partial refunds exceeded the captured amount",
    )


@family("CWE-1284")
def bound_negative_qty(c: Ctx) -> Sample:
    path = "/cart/items"
    if c.fw == "express":
        v = js_route(
            c,
            "POST",
            path,
            "  cart.add(req.body.sku, Number(req.body.quantity));\n  res.json(cart.total());\n",
        )
        f = js_route(
            c,
            "POST",
            path,
            "  const q = Number(req.body.quantity);\n  if (!Number.isInteger(q) || q < 1 || q > 100) return res.sendStatus(400);\n  cart.add(req.body.sku, q);\n  res.json(cart.total());\n",
        )
        p = js_route(
            c,
            "POST",
            path,
            "  const q = Number(req.body.quantity);\n  if (q > 100) return res.sendStatus(400);\n  cart.add(req.body.sku, q);\n  res.json(cart.total());\n",
        )
    else:
        v = py_route(
            c,
            "POST",
            path,
            "body: CartItem",
            '    cart.add(body.sku, body.quantity)\n    return {"total": cart.total()}\n',
        )
        f = py_route(
            c,
            "POST",
            path,
            "body: CartItem",
            '    if not 1 <= body.quantity <= 100:\n        raise BadRequest()\n    cart.add(body.sku, body.quantity)\n    return {"total": cart.total()}\n',
        )
        p = py_route(
            c,
            "POST",
            path,
            "body: CartItem",
            '    if body.quantity > 100:\n        raise BadRequest()\n    cart.add(body.sku, body.quantity)\n    return {"total": cart.total()}\n',
        )
    return Sample(
        "bound_negative_qty",
        "CWE-1284",
        c.fw,
        v,
        f,
        p,
        "missing_check",
        "validate_range",
        "WSTG-BUSL-01",
        "quantity=-5 produced a negative total",
    )


@family("CWE-1284")
def bound_transfer(c: Ctx) -> Sample:
    path = "/transfers"
    if c.fw == "express":
        v = js_route(
            c,
            "POST",
            path,
            "  await ledger.move(req.user.id, req.body.to, req.body.amount);\n  res.sendStatus(201);\n",
        )
        f = js_route(
            c,
            "POST",
            path,
            "  const bal = await ledger.balance(req.user.id);\n  if (req.body.amount <= 0 || req.body.amount > bal) return res.sendStatus(400);\n  await ledger.move(req.user.id, req.body.to, req.body.amount);\n  res.sendStatus(201);\n",
        )
        p = js_route(
            c,
            "POST",
            path,
            "  if (req.body.amount <= 0) return res.sendStatus(400);\n  await ledger.move(req.user.id, req.body.to, req.body.amount);\n  res.sendStatus(201);\n",
        )
    else:
        v = py_route(
            c,
            "POST",
            path,
            "body: Transfer",
            f"    ledger.move({c.user}.id, body.to, body.amount)\n",
        )
        f = py_route(
            c,
            "POST",
            path,
            "body: Transfer",
            f"    if body.amount <= 0 or body.amount > ledger.balance({c.user}.id):\n        raise BadRequest()\n    ledger.move({c.user}.id, body.to, body.amount)\n",
        )
        p = py_route(
            c,
            "POST",
            path,
            "body: Transfer",
            f"    if body.amount <= 0:\n        raise BadRequest()\n    ledger.move({c.user}.id, body.to, body.amount)\n",
        )
    return Sample(
        "bound_transfer",
        "CWE-1284",
        c.fw,
        v,
        f,
        p,
        "missing_check",
        "validate_range",
        "WSTG-BUSL-01",
        "a transfer larger than the balance succeeded",
    )


@family("CWE-1284")
def bound_page_size(c: Ctx) -> Sample:
    path = f"/{c.res}s"
    if c.fw == "express":
        v = js_route(
            c,
            "GET",
            path,
            f"  res.json(await {c.Res}.findAll({{ limit: Number(req.query.limit) }}));\n",
        )
        f = js_route(
            c,
            "GET",
            path,
            f"  const limit = Math.min(Math.max(Number(req.query.limit) || 20, 1), 100);\n  res.json(await {c.Res}.findAll({{ limit }}));\n",
        )
        p = js_route(
            c,
            "GET",
            path,
            f"  const limit = Number(req.query.limit) || 20;\n  res.json(await {c.Res}.findAll({{ limit }}));\n",
        )
    else:
        v = py_route(
            c,
            "GET",
            path,
            "limit: int = 20",
            f"    return {c.db}.query({c.Res}).limit(limit).all()\n",
        )
        f = py_route(
            c,
            "GET",
            path,
            "limit: int = Query(20, ge=1, le=100)",
            f"    return {c.db}.query({c.Res}).limit(limit).all()\n",
        )
        p = py_route(
            c,
            "GET",
            path,
            "limit: int = 20",
            f"    limit = limit or 20\n    return {c.db}.query({c.Res}).limit(limit).all()\n",
        )
    return Sample(
        "bound_page_size",
        "CWE-1284",
        c.fw,
        v,
        f,
        p,
        "missing_check",
        "validate_range",
        "WSTG-BUSL-01",
        "limit=1000000 returned the whole table",
    )


# ----------------------------------------------------------------- CWE-942 permissive CORS


@family("CWE-942")
def cors_star_credentials(c: Ctx) -> Sample:
    if c.fw == "express":
        v = "app.use(cors({ origin: true, credentials: true }));\n"
        f = "app.use(cors({ origin: ['https://app.example.com'], credentials: true }));\n"
        p = "app.use(cors({ origin: /example\\.com/, credentials: true }));\n"
    elif c.fw == "fastapi":
        v = 'app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"])\n'
        f = 'app.add_middleware(CORSMiddleware, allow_origins=[settings.frontend_origin], allow_credentials=True, allow_methods=["GET", "POST"])\n'
        p = 'app.add_middleware(CORSMiddleware, allow_origin_regex=r".*example\\.com", allow_credentials=True)\n'
    else:
        v = 'CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)\n'
        f = 'CORS(app, resources={r"/api/*": {"origins": [FRONTEND_ORIGIN]}}, supports_credentials=True)\n'
        p = 'CORS(app, resources={r"/*": {"origins": r".*example.com"}}, supports_credentials=True)\n'
    return Sample(
        "cors_star_credentials",
        "CWE-942",
        c.fw,
        v,
        f,
        p,
        "configuration",
        "restrict_cors_origins",
        "WSTG-CLNT-07",
        "an arbitrary Origin received credentialed CORS headers",
    )


@family("CWE-942")
def cors_reflect(c: Ctx) -> Sample:
    if c.fw == "express":
        v = "app.use((req, res, next) => {\n  res.set('Access-Control-Allow-Origin', req.headers.origin);\n  res.set('Access-Control-Allow-Credentials', 'true');\n  next();\n});\n"
        f = "app.use((req, res, next) => {\n  if (ALLOWED_ORIGINS.has(req.headers.origin)) {\n    res.set('Access-Control-Allow-Origin', req.headers.origin);\n    res.set('Access-Control-Allow-Credentials', 'true');\n  }\n  next();\n});\n"
        p = "app.use((req, res, next) => {\n  if (req.headers.origin && req.headers.origin.endsWith('example.com')) res.set('Access-Control-Allow-Origin', req.headers.origin);\n  res.set('Access-Control-Allow-Credentials', 'true');\n  next();\n});\n"
    else:
        v = '@app.after_request\ndef cors(resp):\n    resp.headers["Access-Control-Allow-Origin"] = request.headers.get("Origin", "*")\n    resp.headers["Access-Control-Allow-Credentials"] = "true"\n    return resp\n'
        f = '@app.after_request\ndef cors(resp):\n    origin = request.headers.get("Origin")\n    if origin in ALLOWED_ORIGINS:\n        resp.headers["Access-Control-Allow-Origin"] = origin\n        resp.headers["Access-Control-Allow-Credentials"] = "true"\n    return resp\n'
        p = '@app.after_request\ndef cors(resp):\n    origin = request.headers.get("Origin", "")\n    if origin.endswith("example.com"):\n        resp.headers["Access-Control-Allow-Origin"] = origin\n    resp.headers["Access-Control-Allow-Credentials"] = "true"\n    return resp\n'
    return Sample(
        "cors_reflect",
        "CWE-942",
        c.fw,
        v,
        f,
        p,
        "wrong_check",
        "restrict_cors_origins",
        "WSTG-CLNT-07",
        "the Origin header was reflected with credentials",
    )


@family("CWE-942")
def cors_null(c: Ctx) -> Sample:
    if c.fw == "express":
        v = "const ALLOWED = ['https://app.example.com', 'null'];\napp.use(cors({ origin: ALLOWED, credentials: true }));\n"
        f = "const ALLOWED = ['https://app.example.com'];\napp.use(cors({ origin: ALLOWED, credentials: true }));\n"
        p = "const ALLOWED = ['https://app.example.com', 'null', 'http://localhost:3000'];\napp.use(cors({ origin: ALLOWED, credentials: true }));\n"
    else:
        v = 'ALLOWED_ORIGINS = ["https://app.example.com", "null"]\napp.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_credentials=True)\n'
        f = 'ALLOWED_ORIGINS = ["https://app.example.com"]\napp.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_credentials=True)\n'
        p = 'ALLOWED_ORIGINS = ["https://app.example.com", "null", "http://localhost:3000"]\napp.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_credentials=True)\n'
    return Sample(
        "cors_null",
        "CWE-942",
        c.fw,
        v,
        f,
        p,
        "configuration",
        "restrict_cors_origins",
        "WSTG-CLNT-07",
        "Origin: null was trusted with credentials",
    )


@family("CWE-942")
def cors_wildcard_subdomain(c: Ctx) -> Sample:
    if c.fw == "express":
        v = "app.use(cors({ origin: (o, cb) => cb(null, !o || o.includes('example')), credentials: true }));\n"
        f = "app.use(cors({ origin: (o, cb) => cb(null, !o || /^https:\\/\\/([a-z]+\\.)?example\\.com$/.test(o)), credentials: true }));\n"
        p = "app.use(cors({ origin: (o, cb) => cb(null, !o || o.endsWith('example.com')), credentials: true }));\n"
    else:
        v = 'app.add_middleware(CORSMiddleware, allow_origin_regex=r"https?://.*example.*", allow_credentials=True)\n'
        f = 'app.add_middleware(CORSMiddleware, allow_origin_regex=r"^https://([a-z0-9-]+\\.)?example\\.com$", allow_credentials=True)\n'
        p = 'app.add_middleware(CORSMiddleware, allow_origin_regex=r"https://.*example\\.com", allow_credentials=True)\n'
    return Sample(
        "cors_wildcard_subdomain",
        "CWE-942",
        c.fw,
        v,
        f,
        p,
        "wrong_check",
        "restrict_cors_origins",
        "WSTG-CLNT-07",
        "https://example.attacker.net was trusted",
    )


# corpus-2 families (this import registers them in FAMILIES); placed after the helpers.
from . import corpus_variants as _corpus_variants  # noqa: F401,E402

# ----------------------------------------------------------------- generation

CLASSES = sorted(FAMILIES)
SAFE = "safe"


def generate(per_family: int = 36, seed: int = 20261018, test_family: int = 3) -> list[dict]:
    """All samples, deterministic. Family ``test_family`` of each class is the test split."""
    rng = random.Random(seed)
    rows: list[dict] = []
    for cwe in CLASSES:
        for index, fam in enumerate(FAMILIES[cwe]):
            for n in range(per_family):
                # Family 3 is never seen in training. Families 0-2 train, with every 6th sample
                # held out as in-distribution validation for early stopping.
                split = "test" if index == test_family else ("val" if n % 6 == 5 else "train")
                fw = FRAMEWORKS[n % len(FRAMEWORKS)]
                s = fam(Ctx(rng, fw))
                rows.append(
                    {
                        "id": f"{s.family}-{n}",
                        "family": s.family,
                        "split": split,
                        "framework": fw,
                        "cwe": cwe,
                        "vulnerable": s.vulnerable,
                        "fixed": s.fixed,
                        "partial": s.partial,
                        "cause": s.cause,
                        "strategy": s.strategy,
                        "probe": s.probe,
                        "observation": s.observation,
                    }
                )
    return rows
