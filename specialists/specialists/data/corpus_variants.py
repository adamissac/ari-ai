"""corpus-2 families: same CWE, different root cause and correct remediation.

The corpus-1 families gave each CWE one dominant (cause, strategy) pair, which made the
labels predictable from the CWE id alone — a lookup table was unbeatable. These families add
a second shape per CWE with a different CauseClass and strategy, so the models must read the
code. Labels stay inside the shared taxonomies (CauseClass for Diagnose).
"""

from __future__ import annotations

from .corpus import Ctx, Sample, family, js_route, py_route


@family("CWE-639")
def idor_scope_claim(c: Ctx) -> Sample:
    """Row exists, but the caller's tenant is taken from a client-supplied claim."""
    path = f"/t/{{tenant}}/{c.res}s/{{{c.idv}}}"
    if c.fw == "express":
        v = js_route(
            c,
            "GET",
            path,
            f"  const {c.var} = await {c.Res}.findOne({{ where: {{ id: req.params.{c.idv}, tenant_id: req.params.tenant }} }});\n  res.json({c.var});\n",
        )
        f = js_route(
            c,
            "GET",
            path,
            f"  const {c.var} = await {c.Res}.findOne({{ where: {{ id: req.params.{c.idv}, tenant_id: req.user.tenant_id }} }});\n  if (!{c.var}) return res.sendStatus(404);\n  res.json({c.var});\n",
        )
        p = js_route(
            c,
            "GET",
            path,
            f"  if (req.params.tenant !== req.user.tenant_id && !req.user.admin) return res.sendStatus(403);\n  res.json(await {c.Res}.findByPk(req.params.{c.idv}));\n",
        )
    else:
        v = py_route(
            c,
            "GET",
            path,
            f"tenant: str, {c.idv}: int",
            f"    return {c.db}.query({c.Res}).filter({c.Res}.id == {c.idv}, {c.Res}.tenant_id == tenant).first()\n",
        )
        f = py_route(
            c,
            "GET",
            path,
            f"tenant: str, {c.idv}: int",
            f"    row = {c.db}.query({c.Res}).filter({c.Res}.id == {c.idv}, {c.Res}.tenant_id == {c.user}.tenant_id).first()\n    if row is None:\n        raise NotFound()\n    return row\n",
        )
        p = py_route(
            c,
            "GET",
            path,
            f"tenant: str, {c.idv}: int",
            f"    if tenant != {c.user}.tenant_id and not {c.user}.admin:\n        raise Forbidden()\n    return {c.db}.get({c.Res}, {c.idv})\n",
        )
    return Sample(
        "idor_scope_claim",
        "CWE-639",
        c.fw,
        v,
        f,
        p,
        "missing_check",
        "bind_authorization_to_session",
        "WSTG-ATHZ-04",
        "a caller passed another tenant slug and read its row",
    )


@family("CWE-639")
def idor_sequential_ref(c: Ctx) -> Sample:
    """Sequential primary key handed to clients; the fix exposes an opaque reference."""
    path = f"/{c.res}s/by-ref/{{ref}}"
    if c.fw == "express":
        v = js_route(
            c, "GET", path, f"  res.json(await {c.Res}.findByPk(Number(req.params.ref)));\n"
        )
        f = js_route(
            c,
            "GET",
            path,
            f"  const id = await refMap.lookup('{c.res}', req.params.ref, req.user.id);\n  if (id === null) return res.sendStatus(404);\n  res.json(await {c.Res}.findByPk(id));\n",
        )
        p = js_route(
            c,
            "GET",
            path,
            f"  const n = Number(req.params.ref);\n  if (!Number.isInteger(n)) return res.sendStatus(400);\n  res.json(await {c.Res}.findByPk(n));\n",
        )
    else:
        v = py_route(c, "GET", path, "ref: str", f"    return {c.db}.get({c.Res}, int(ref))\n")
        f = py_route(
            c,
            "GET",
            path,
            "ref: str",
            f'    ref_id = ref_map.lookup("{c.res}", ref, {c.user}.id)\n    if ref_id is None:\n        raise NotFound()\n    return {c.db}.get({c.Res}, ref_id)\n',
        )
        p = py_route(
            c,
            "GET",
            path,
            "ref: str",
            f"    try:\n        n = int(ref)\n    except ValueError:\n        raise BadRequest() from None\n    return {c.db}.get({c.Res}, n)\n",
        )
    return Sample(
        "idor_sequential_ref",
        "CWE-639",
        c.fw,
        v,
        f,
        p,
        "unsafe_default",
        "indirect_reference_map",
        "WSTG-ATHZ-04",
        f"incrementing the ref returned the next tenant's {c.res}",
    )


@family("CWE-862")
def scope_from_request(c: Ctx) -> Sample:
    """A privileged scope flag arrives inside the request body instead of from the session."""
    path = f"/{c.res}s/search"
    if c.fw == "express":
        v = js_route(
            c,
            "POST",
            path,
            f"  const scope = req.body.scope === 'all' ? {{}} : {{ {c.owner}: req.user.id }};\n  res.json(await {c.Res}.findAll({{ where: scope }}));\n",
        )
        f = js_route(
            c,
            "POST",
            path,
            f"  const scope = req.user.roles.includes('admin') && req.body.scope === 'all' ? {{}} : {{ {c.owner}: req.user.id }};\n  res.json(await {c.Res}.findAll({{ where: scope }}));\n",
        )
        p = js_route(
            c,
            "POST",
            path,
            f"  if (req.body.scope === 'all' && !req.body.confirm) return res.sendStatus(400);\n  res.json(await {c.Res}.findAll());\n",
        )
    else:
        v = py_route(
            c,
            "POST",
            path,
            "body: SearchRequest",
            f'    scope = {{}} if body.scope == "all" else {{"{c.owner}": {c.user}.id}}\n    return {c.db}.query({c.Res}).filter_by(**scope).all()\n',
        )
        f = py_route(
            c,
            "POST",
            path,
            "body: SearchRequest",
            f'    scope = {{}} if "admin" in {c.user}.roles and body.scope == "all" else {{"{c.owner}": {c.user}.id}}\n    return {c.db}.query({c.Res}).filter_by(**scope).all()\n',
        )
        p = py_route(
            c,
            "POST",
            path,
            "body: SearchRequest",
            f'    if body.scope == "all" and not body.confirm:\n        raise BadRequest()\n    return {c.db}.query({c.Res}).all()\n',
        )
    return Sample(
        "scope_from_request",
        "CWE-862",
        c.fw,
        v,
        f,
        p,
        "logic_error",
        "derive_scope_server_side",
        "WSTG-ATHZ-02",
        "a basic user sent scope=all and received every tenant's rows",
    )


@family("CWE-862")
def route_default_permit(c: Ctx) -> Sample:
    """A permission resolver whose default branch permits unknown actions."""
    path = f"/{c.res}s/{{{c.idv}}}/action"
    if c.fw == "express":
        v = js_route(
            c,
            "POST",
            path,
            f"  const allowed = req.body.action === 'read' ? isOwner(req.user, req.params.{c.idv}) : true;\n  if (!allowed) return res.sendStatus(403);\n  await applyAction(req.body.action, req.params.{c.idv});\n  res.sendStatus(204);\n",
        )
        f = js_route(
            c,
            "POST",
            path,
            f"  const rules = {{ read: 'owner', export: 'owner', publish: 'editor' }};\n  const need = rules[req.body.action];\n  if (!need || !hasRole(req.user, need)) return res.sendStatus(403);\n  await applyAction(req.body.action, req.params.{c.idv});\n  res.sendStatus(204);\n",
        )
        p = js_route(
            c,
            "POST",
            path,
            f"  if (req.body.action === 'admin_wipe') return res.sendStatus(403);\n  await applyAction(req.body.action, req.params.{c.idv});\n  res.sendStatus(204);\n",
        )
    else:
        v = py_route(
            c,
            "POST",
            path,
            f"{c.idv}: int, body: Action",
            f'    allowed = is_owner({c.user}, {c.idv}) if body.action == "read" else True\n    if not allowed:\n        raise Forbidden()\n    apply_action(body.action, {c.idv})\n',
        )
        f = py_route(
            c,
            "POST",
            path,
            f"{c.idv}: int, body: Action",
            f'    rules = {{"read": "owner", "export": "owner", "publish": "editor"}}\n    need = rules.get(body.action)\n    if need is None or not has_role({c.user}, need):\n        raise Forbidden()\n    apply_action(body.action, {c.idv})\n',
        )
        p = py_route(
            c,
            "POST",
            path,
            f"{c.idv}: int, body: Action",
            f'    if body.action == "admin_wipe":\n        raise Forbidden()\n    apply_action(body.action, {c.idv})\n',
        )
    return Sample(
        "route_default_permit",
        "CWE-862",
        c.fw,
        v,
        f,
        p,
        "logic_error",
        "deny_by_default",
        "WSTG-ATHZ-02",
        "an unlisted action name bypassed the permission resolver",
    )


@family("CWE-89")
def sqli_like_clause(c: Ctx) -> Sample:
    """Parameterised value, but LIKE wildcards in it are still attacker-controlled."""
    path = f"/{c.res}s/match"
    if c.fw == "express":
        v = js_route(
            c,
            "GET",
            path,
            f"  res.json((await pool.query('SELECT * FROM {c.table} WHERE name LIKE ?', ['%' + req.query.q + '%'])).rows);\n",
        )
        f = js_route(
            c,
            "GET",
            path,
            f"  const q = req.query.q.replace(/[%_\\\\]/g, (m) => '\\\\' + m);\n  res.json((await pool.query(\"SELECT * FROM {c.table} WHERE name LIKE ? ESCAPE '\\\\'\", ['%' + q + '%'])).rows);\n",
        )
        p = js_route(
            c,
            "GET",
            path,
            f"  const q = req.query.q.slice(0, 10);\n  res.json((await pool.query('SELECT * FROM {c.table} WHERE name LIKE ?', ['%' + q + '%'])).rows);\n",
        )
    else:
        v = py_route(
            c,
            "GET",
            path,
            "q: str",
            f'    return {c.db}.execute("SELECT * FROM {c.table} WHERE name LIKE :p", {{"p": "%" + q + "%"}}).fetchall()\n',
        )
        f = py_route(
            c,
            "GET",
            path,
            "q: str",
            f'    esc = q.replace("\\\\", "\\\\\\\\").replace("%", "\\\\%").replace("_", "\\\\_")\n    return {c.db}.execute("SELECT * FROM {c.table} WHERE name LIKE :p ESCAPE \'\\\\\'", {{"p": "%" + esc + "%"}}).fetchall()\n',
        )
        p = py_route(
            c,
            "GET",
            path,
            "q: str",
            f'    return {c.db}.execute("SELECT * FROM {c.table} WHERE name LIKE :p", {{"p": "%" + q[:10] + "%"}}).fetchall()\n',
        )
    return Sample(
        "sqli_like_clause",
        "CWE-89",
        c.fw,
        v,
        f,
        p,
        "wrong_check",
        "escape_like_wildcards",
        "WSTG-INPV-05",
        "a % wildcard in q turned a prefix match into a full table scan",
    )


@family("CWE-89")
def sqli_in_clause(c: Ctx) -> Sample:
    """An IN (...) list built by joining user ids."""
    path = f"/{c.res}s/bulk"
    if c.fw == "express":
        v = js_route(
            c,
            "POST",
            path,
            f"  const ids = req.body.ids.join(',');\n  res.json((await pool.query('SELECT * FROM {c.table} WHERE id IN (' + ids + ')')).rows);\n",
        )
        f = js_route(
            c,
            "POST",
            path,
            f"  const ids = req.body.ids.map(Number).filter(Number.isInteger);\n  res.json((await pool.query('SELECT * FROM {c.table} WHERE id = ANY($1::int[])', [ids])).rows);\n",
        )
        p = js_route(
            c,
            "POST",
            path,
            f"  const ids = req.body.ids.map((x) => parseInt(x)).join(',');\n  res.json((await pool.query('SELECT * FROM {c.table} WHERE id IN (' + ids + ')')).rows);\n",
        )
    else:
        v = py_route(
            c,
            "POST",
            path,
            "body: BulkRequest",
            f'    ids = ",".join(body.ids)\n    return {c.db}.execute("SELECT * FROM {c.table} WHERE id IN (" + ids + "").fetchall()\n',
        )
        f = py_route(
            c,
            "POST",
            path,
            "body: BulkRequest",
            f'    ids = [int(x) for x in body.ids]\n    marks = ",".join("?" for _ in ids)\n    return {c.db}.execute("SELECT * FROM {c.table} WHERE id IN (" + marks + "", tuple(ids)).fetchall()\n',
        )
        p = py_route(
            c,
            "POST",
            path,
            "body: BulkRequest",
            f'    ids = ",".join(str(int(x)) for x in body.ids if str(x).isdigit())\n    return {c.db}.execute("SELECT * FROM {c.table} WHERE id IN (" + ids + "").fetchall()\n',
        )
    return Sample(
        "sqli_in_clause",
        "CWE-89",
        c.fw,
        v,
        f,
        p,
        "logic_error",
        "expand_bind_params",
        "WSTG-INPV-05",
        "a second value in ids broke out of the list and dropped the WHERE",
    )


@family("CWE-78")
def cmd_user_tool(c: Ctx) -> Sample:
    """The tool name itself comes from the request."""
    path = f"/{c.res}s/lint"
    if c.fw == "express":
        v = js_route(
            c, "POST", path, "  exec(req.body.linter + ' ' + TMPFILE, (e, out) => res.send(out));\n"
        )
        f = js_route(
            c,
            "POST",
            path,
            "  const linter = ['eslint', 'shellcheck'].includes(req.body.linter) ? req.body.linter : null;\n  if (!linter) return res.sendStatus(400);\n  execFile(linter, [TMPFILE], (e, out) => res.send(out));\n",
        )
        p = js_route(
            c,
            "POST",
            path,
            "  if (!/^[a-z]+$/.test(req.body.linter)) return res.sendStatus(400);\n  exec(req.body.linter + ' ' + TMPFILE, (e, out) => res.send(out));\n",
        )
    else:
        v = py_route(
            c, "POST", path, "body: LintRequest", '    os.system(body.linter + " " + TMPFILE)\n'
        )
        f = py_route(
            c,
            "POST",
            path,
            "body: LintRequest",
            '    if body.linter not in {"flake8", "shellcheck"}:\n        raise BadRequest()\n    subprocess.run([body.linter, TMPFILE], check=False)\n',
        )
        p = py_route(
            c,
            "POST",
            path,
            "body: LintRequest",
            '    if not body.linter.isalpha():\n        raise BadRequest()\n    os.system(body.linter + " " + TMPFILE)\n',
        )
    return Sample(
        "cmd_user_tool",
        "CWE-78",
        c.fw,
        v,
        f,
        p,
        "wrong_check",
        "allowlist_command",
        "WSTG-INPV-12",
        "linter=cat /etc/passwd ran an arbitrary binary",
    )


@family("CWE-22")
def path_symlink_escape(c: Ctx) -> Sample:
    """Joining under a root is not enough when an attacker can plant a symlink."""
    path = f"/{c.res}s/file"
    if c.fw == "express":
        v = js_route(c, "GET", path, "  res.sendFile(path.join(UPLOAD_ROOT, req.query.name));\n")
        f = js_route(
            c,
            "GET",
            path,
            "  const real = fs.realpathSync(path.join(UPLOAD_ROOT, req.query.name));\n  if (!real.startsWith(fs.realpathSync(UPLOAD_ROOT) + path.sep)) return res.sendStatus(403);\n  res.sendFile(real);\n",
        )
        p = js_route(
            c,
            "GET",
            path,
            "  const safe = req.query.name.replace(/\\.\\./g, '');\n  res.sendFile(path.join(UPLOAD_ROOT, safe));\n",
        )
    else:
        v = py_route(c, "GET", path, "name: str", "    return FileResponse(UPLOAD_ROOT / name)\n")
        f = py_route(
            c,
            "GET",
            path,
            "name: str",
            "    real = (UPLOAD_ROOT / name).resolve()\n    if UPLOAD_ROOT.resolve() not in real.parents:\n        raise Forbidden()\n    return FileResponse(real)\n",
        )
        p = py_route(
            c,
            "GET",
            path,
            "name: str",
            '    safe = name.replace("..", "")\n    return FileResponse(UPLOAD_ROOT / safe)\n',
        )
    return Sample(
        "path_symlink_escape",
        "CWE-22",
        c.fw,
        v,
        f,
        p,
        "wrong_check",
        "check_realpath_and_scope",
        "WSTG-ATHZ-01",
        "a symlinked name resolved outside the upload root",
    )


@family("CWE-22")
def path_template_slot(c: Ctx) -> Sample:
    """A template filename is chosen by the client and formatted into the path."""
    path = f"/{c.res}s/render"
    if c.fw == "express":
        v = js_route(c, "GET", path, "  res.render('templates/' + req.query.tpl + '.ejs');\n")
        f = js_route(
            c,
            "GET",
            path,
            "  const tpl = ALLOWED_TEMPLATES[req.query.tpl];\n  if (!tpl) return res.sendStatus(404);\n  res.render(tpl);\n",
        )
        p = js_route(
            c,
            "GET",
            path,
            "  if (req.query.tpl.includes('/')) return res.sendStatus(400);\n  res.render('templates/' + req.query.tpl + '.ejs');\n",
        )
    else:
        v = py_route(c, "GET", path, "tpl: str", '    return render("templates/%s.html" % tpl)\n')
        f = py_route(
            c,
            "GET",
            path,
            "tpl: str",
            "    name = ALLOWED_TEMPLATES.get(tpl)\n    if name is None:\n        raise NotFound()\n    return render(name)\n",
        )
        p = py_route(
            c,
            "GET",
            path,
            "tpl: str",
            '    if "/" in tpl:\n        raise BadRequest()\n    return render("templates/%s.html" % tpl)\n',
        )
    return Sample(
        "path_template_slot",
        "CWE-22",
        c.fw,
        v,
        f,
        p,
        "wrong_check",
        "allowlist_identifier",
        "WSTG-ATHZ-01",
        "tpl=../../etc/secret rendered a file outside the template dir",
    )


@family("CWE-79")
def xss_attribute_ctx(c: Ctx) -> Sample:
    """Value lands inside a quoted HTML attribute, so < > escaping is insufficient."""
    path = f"/{c.res}s/badge"
    if c.fw == "express":
        v = js_route(
            c,
            "GET",
            path,
            "  res.send('<img alt=' + String.fromCharCode(34) + req.query.alt + String.fromCharCode(34) + '>');\n",
        )
        f = js_route(
            c,
            "GET",
            path,
            "  res.send('<img alt=' + String.fromCharCode(34) + escapeAttr(req.query.alt) + String.fromCharCode(34) + '>');\n",
        )
        p = js_route(
            c,
            "GET",
            path,
            "  res.send('<img alt=' + String.fromCharCode(34) + req.query.alt.replace(/</g, '') + String.fromCharCode(34) + '>');\n",
        )
    else:
        v = py_route(
            c, "GET", path, "alt: str", "    return HTMLResponse('<img alt=\"%s\">' % alt)\n"
        )
        f = py_route(
            c,
            "GET",
            path,
            "alt: str",
            "    return HTMLResponse('<img alt=\"%s\">' % html.escape(alt, quote=True))\n",
        )
        p = py_route(
            c,
            "GET",
            path,
            "alt: str",
            "    return HTMLResponse('<img alt=\"%s\">' % alt.replace('<', ''))\n",
        )
    return Sample(
        "xss_attribute_ctx",
        "CWE-79",
        c.fw,
        v,
        f,
        p,
        "wrong_check",
        "contextual_escape",
        "WSTG-INPV-01",
        "a double quote in alt closed the attribute and injected an event handler",
    )


@family("CWE-79")
def xss_json_in_script(c: Ctx) -> Sample:
    """JSON embedded raw inside a <script> block."""
    path = f"/{c.res}s/embed"
    if c.fw == "express":
        v = js_route(
            c,
            "GET",
            path,
            "  res.send('<script>window.obj = ' + JSON.stringify(req.query.state) + ';</script>');\n",
        )
        f = js_route(
            c,
            "GET",
            path,
            "  const safe = JSON.stringify(req.query.state).replace(/</g, '\\\\u003c');\n  res.send('<script>window.obj = ' + safe + ';</script>');\n",
        )
        p = js_route(
            c,
            "GET",
            path,
            "  res.send('<script>window.obj = ' + JSON.stringify(String(req.query.state)) + ';</script>');\n",
        )
    else:
        v = py_route(
            c,
            "GET",
            path,
            "state: str",
            '    return HTMLResponse("<script>var obj = %s;</script>" % json.dumps(state))\n',
        )
        f = py_route(
            c,
            "GET",
            path,
            "state: str",
            '    payload = json.dumps(state).replace("<", "\\\\u003c")\n    return HTMLResponse("<script>var obj = %s;</script>" % payload)\n',
        )
        p = py_route(
            c,
            "GET",
            path,
            "state: str",
            '    return HTMLResponse("<script>var obj = %s;</script>" % json.dumps(str(state)))\n',
        )
    return Sample(
        "xss_json_in_script",
        "CWE-79",
        c.fw,
        v,
        f,
        p,
        "logic_error",
        "safe_json_serialization",
        "WSTG-INPV-01",
        "state=</script><img src=x onerror=alert(1)> broke out of the script block",
    )


@family("CWE-502")
def deser_unsigned_blob(c: Ctx) -> Sample:
    """A session blob is decoded with no integrity check."""
    path = "/session/restore"
    if c.fw == "express":
        v = js_route(
            c,
            "POST",
            path,
            "  const session = JSON.parse(Buffer.from(req.body.token, 'base64').toString());\n  req.session.restore(session);\n  res.sendStatus(204);\n",
        )
        f = js_route(
            c,
            "POST",
            path,
            "  const token = verifyMac(req.body.token, process.env.SESSION_KEY);\n  if (!token) return res.sendStatus(401);\n  req.session.restore(JSON.parse(token));\n  res.sendStatus(204);\n",
        )
        p = js_route(
            c,
            "POST",
            path,
            "  const session = JSON.parse(Buffer.from(req.body.token, 'base64').toString());\n  if (session.exp < Date.now()) return res.sendStatus(401);\n  req.session.restore(session);\n  res.sendStatus(204);\n",
        )
    else:
        v = py_route(
            c,
            "POST",
            path,
            "body: Token",
            "    session = json.loads(base64.b64decode(body.token))\n    restore_session(session)\n",
        )
        f = py_route(
            c,
            "POST",
            path,
            "body: Token",
            "    raw = verify_mac(body.token, settings.session_key)\n    if raw is None:\n        raise Unauthorized()\n    restore_session(json.loads(raw))\n",
        )
        p = py_route(
            c,
            "POST",
            path,
            "body: Token",
            '    session = json.loads(base64.b64decode(body.token))\n    if session.get("exp", 0) < time.time():\n        raise Unauthorized()\n    restore_session(session)\n',
        )
    return Sample(
        "deser_unsigned_blob",
        "CWE-502",
        c.fw,
        v,
        f,
        p,
        "missing_check",
        "integrity_sign_serialized",
        "WSTG-INPV-11",
        "a forged base64 token restored an administrator session",
    )


@family("CWE-502")
def deser_task_spec(c: Ctx) -> Sample:
    """A queued job spec is parsed with a full object loader."""
    path = f"/{c.res}s/jobs"
    if c.fw == "express":
        v = js_route(
            c,
            "POST",
            path,
            "  const spec = require('js-yaml').load(req.body.spec);\n  queue.enqueue(spec);\n  res.sendStatus(202);\n",
        )
        f = js_route(
            c,
            "POST",
            path,
            "  const spec = jobSchema.parse(require('js-yaml').load(req.body.spec, { schema: require('js-yaml').JSON_SCHEMA }));\n  queue.enqueue(spec);\n  res.sendStatus(202);\n",
        )
        p = js_route(
            c,
            "POST",
            path,
            "  if (req.body.spec.includes('exec')) return res.sendStatus(400);\n  queue.enqueue(require('js-yaml').load(req.body.spec));\n  res.sendStatus(202);\n",
        )
    else:
        v = py_route(
            c,
            "POST",
            path,
            "body: JobSpec",
            "    spec = yaml.load(body.spec)\n    queue.enqueue(spec)\n",
        )
        f = py_route(
            c,
            "POST",
            path,
            "body: JobSpec",
            "    spec = JobPayload.model_validate(yaml.safe_load(body.spec))\n    queue.enqueue(spec.model_dump())\n",
        )
        p = py_route(
            c,
            "POST",
            path,
            "body: JobSpec",
            '    if "exec" in body.spec:\n        raise BadRequest()\n    queue.enqueue(yaml.load(body.spec))\n',
        )
    return Sample(
        "deser_task_spec",
        "CWE-502",
        c.fw,
        v,
        f,
        p,
        "wrong_check",
        "schema_validate_payload",
        "WSTG-INPV-11",
        "a crafted tag in the spec ran code on the worker",
    )


@family("CWE-798")
def secret_ci_config(c: Ctx) -> Sample:
    """A service URL with an embedded password committed in config."""
    if c.fw == "express":
        v = f"const config = {{\n  db: process.env.CI_DB_URL || 'postgres://app:s3cret-ci@db.internal/{c.res}',\n}};\n"
        f = f"const config = {{\n  db: process.env.CI_DB_URL || secrets.ref('{c.res}-db-url'),\n}};\n"
        p = f"const config = {{\n  db: process.env.CI_DB_URL || 'postgres://app:s3cret-ci@db.internal/{c.res}',\n  env: 'test',\n}};\n"
    else:
        v = f'DB_URL = os.getenv("CI_DB_URL", "postgres://app:s3cret-ci@db.internal/{c.res}")\n'
        f = f'DB_URL = os.getenv("CI_DB_URL") or secret_ref("{c.res}-db-url")\n'
        p = f'ENV = "test"\nDB_URL = os.getenv("CI_DB_URL", "postgres://app:s3cret-ci@db.internal/{c.res}")\n'
    return Sample(
        "secret_ci_config",
        "CWE-798",
        c.fw,
        v,
        f,
        p,
        "configuration",
        "use_secret_manager_reference",
        "WSTG-ATHN-02",
        "the repository history contains a live database password",
    )


@family("CWE-916")
def pw_fast_hash(c: Ctx) -> Sample:
    """Passwords hashed with a fast general-purpose digest."""
    if c.fw == "express":
        v = "  const ok = crypto.createHash('sha256').update(req.body.password).digest('hex') === user.password_hash;\n"
        f = "  const ok = await argon2.verify(user.password_hash, req.body.password);\n"
        p = "  const ok = crypto.createHash('sha256').update(req.body.password + STATIC_SALT).digest('hex') === user.password_hash;\n"
    else:
        v = "    ok = hashlib.sha256(body.password.encode()).hexdigest() == user.password_hash\n"
        f = "    ok = argon2.verify(user.password_hash, body.password)\n"
        p = "    ok = hashlib.sha256((body.password + STATIC_SALT).encode()).hexdigest() == user.password_hash\n"
    return Sample(
        "pw_fast_hash",
        "CWE-916",
        c.fw,
        v,
        f,
        p,
        "unsafe_default",
        "memory_hard_kdf",
        "WSTG-CRYP-04",
        "a dumped hash was cracked offline in minutes",
    )


@family("CWE-916")
def pw_global_salt(c: Ctx) -> Sample:
    """A single application-wide salt, so identical passwords share a hash."""
    if c.fw == "express":
        v = "  const h = crypto.createHash('sha256').update(APP_SALT + req.body.password).digest('hex');\n"
        f = "  const h = await bcrypt.hash(req.body.password, 12);\n"
        p = "  const h = crypto.createHash('sha256').update(APP_SALT + APP_PEPPER + req.body.password).digest('hex');\n"
    else:
        v = "    h = hashlib.sha256((APP_SALT + body.password).encode()).hexdigest()\n"
        f = "    h = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt(12))\n"
        p = "    h = hashlib.sha256((APP_SALT + APP_PEPPER + body.password).encode()).hexdigest()\n"
    return Sample(
        "pw_global_salt",
        "CWE-916",
        c.fw,
        v,
        f,
        p,
        "wrong_check",
        "per_user_salt",
        "WSTG-CRYP-04",
        "two accounts with the same password have the same stored hash",
    )


@family("CWE-918")
def ssrf_follow_redirect(c: Ctx) -> Sample:
    """The initial URL is allow-listed, but a redirect target is not re-checked."""
    path = f"/{c.res}s/preview"
    if c.fw == "express":
        v = js_route(
            c,
            "GET",
            path,
            "  if (!isPublicUrl(req.query.url)) return res.sendStatus(400);\n  const page = await fetch(req.query.url, { redirect: 'follow' });\n  res.send(await page.text());\n",
        )
        f = js_route(
            c,
            "GET",
            path,
            "  const page = await fetchChecked(req.query.url, { policy: allowlistPolicy, revalidateEachHop: true });\n  res.send(await page.text());\n",
        )
        p = js_route(
            c,
            "GET",
            path,
            "  const u = new URL(req.query.url);\n  if (!isPublicUrl(u.origin)) return res.sendStatus(400);\n  const page = await fetch(req.query.url, { redirect: 'follow' });\n  res.send(await page.text());\n",
        )
    else:
        v = py_route(
            c,
            "GET",
            path,
            "url: str",
            "    if not is_public_url(url):\n        raise BadRequest()\n    return Response(requests.get(url, timeout=5).content)\n",
        )
        f = py_route(
            c,
            "GET",
            path,
            "url: str",
            "    return Response(fetch_checked(url, policy=ALLOWLIST, revalidate_each_hop=True).content)\n",
        )
        p = py_route(
            c,
            "GET",
            path,
            "url: str",
            "    u = urlparse(url)\n    if not is_public_url(u.netloc):\n        raise BadRequest()\n    return Response(requests.get(url, timeout=5).content)\n",
        )
    return Sample(
        "ssrf_follow_redirect",
        "CWE-918",
        c.fw,
        v,
        f,
        p,
        "wrong_check",
        "validate_after_redirect",
        "WSTG-INPV-19",
        "an allow-listed host redirected to 169.254.169.254 and leaked metadata",
    )


@family("CWE-942")
def cors_suffix_match(c: Ctx) -> Sample:
    """Origin check accepts any domain that ends with the trusted name."""
    if c.fw == "express":
        v = "app.use(cors({ origin: (o, cb) => cb(null, !!o && o.endsWith('acme.io')), credentials: true }));\n"
        f = "app.use(cors({ origin: ['https://app.acme.io', 'https://admin.acme.io'], credentials: true }));\n"
        p = "app.use(cors({ origin: (o, cb) => cb(null, !!o && o.endsWith('.acme.io')), credentials: true }));\n"
    else:
        v = 'app.add_middleware(CORSMiddleware, allow_origin_regex=r"https?://.*acme\\.io$", allow_credentials=True)\n'
        f = 'app.add_middleware(CORSMiddleware, allow_origins=["https://app.acme.io", "https://admin.acme.io"], allow_credentials=True)\n'
        p = 'app.add_middleware(CORSMiddleware, allow_origin_regex=r"https?://[a-z]+\\.acme\\.io$", allow_credentials=True)\n'
    return Sample(
        "cors_suffix_match",
        "CWE-942",
        c.fw,
        v,
        f,
        p,
        "wrong_check",
        "exact_match_origin_list",
        "WSTG-CLNT-07",
        "https://evil-acme.io was trusted with credentials",
    )


@family("CWE-1284")
def bound_running_total(c: Ctx) -> Sample:
    """A running total can silently wrap past its maximum."""
    path = f"/{c.res}s/split"
    if c.fw == "express":
        v = js_route(
            c,
            "POST",
            path,
            "  const total = req.body.parts.reduce((a, x) => a + x, 0);\n  await ledger.split(req.user.id, total);\n  res.sendStatus(204);\n",
        )
        f = js_route(
            c,
            "POST",
            path,
            "  if (req.body.parts.length > 100 || req.body.parts.some((x) => !Number.isSafeInteger(x) || x < 0)) return res.sendStatus(400);\n  const total = req.body.parts.reduce((a, x) => { if (a > MAX_TOTAL - x) throw new RangeError(); return a + x; }, 0);\n  await ledger.split(req.user.id, total);\n  res.sendStatus(204);\n",
        )
        p = js_route(
            c,
            "POST",
            path,
            "  const total = req.body.parts.reduce((a, x) => a + Math.min(x, 1000), 0);\n  await ledger.split(req.user.id, total);\n  res.sendStatus(204);\n",
        )
    else:
        v = py_route(
            c,
            "POST",
            path,
            "body: SplitRequest",
            "    total = sum(body.parts)\n    ledger.split(user.id, total)\n",
        )
        f = py_route(
            c,
            "POST",
            path,
            "body: SplitRequest",
            "    if len(body.parts) > 100 or any(not isinstance(x, int) or x < 0 for x in body.parts):\n        raise BadRequest()\n    total = 0\n    for x in body.parts:\n        if x > MAX_TOTAL - total:\n            raise BadRequest()\n        total += x\n    ledger.split(user.id, total)\n",
        )
        p = py_route(
            c,
            "POST",
            path,
            "body: SplitRequest",
            "    total = sum(min(x, 1000) for x in body.parts)\n    ledger.split(user.id, total)\n",
        )
    return Sample(
        "bound_running_total",
        "CWE-1284",
        c.fw,
        v,
        f,
        p,
        "logic_error",
        "check_arithmetic_bounds",
        "WSTG-BUSL-01",
        "a crafted parts list wrapped the total below the limit",
    )


@family("CWE-1284")
def bound_state_dependent(c: Ctx) -> Sample:
    """A discount is applied twice because no invariant ties it to order state."""
    path = f"/{c.res}s/{{{c.idv}}}/discount"
    if c.fw == "express":
        v = js_route(
            c,
            "POST",
            path,
            f"  const o = await {c.Res}.findByPk(req.params.{c.idv});\n  o.total -= req.body.amount;\n  await o.save();\n  res.sendStatus(204);\n",
        )
        f = js_route(
            c,
            "POST",
            path,
            f"  const o = await {c.Res}.findByPk(req.params.{c.idv});\n  if (o.discount_applied || req.body.amount < 0 || req.body.amount > o.total) return res.sendStatus(409);\n  o.total -= req.body.amount;\n  o.discount_applied = true;\n  await o.save();\n  res.sendStatus(204);\n",
        )
        p = js_route(
            c,
            "POST",
            path,
            f"  const o = await {c.Res}.findByPk(req.params.{c.idv});\n  if (req.body.amount < 0) return res.sendStatus(400);\n  o.total -= req.body.amount;\n  await o.save();\n  res.sendStatus(204);\n",
        )
    else:
        v = py_route(
            c,
            "POST",
            path,
            f"{c.idv}: int, body: Discount",
            f"    o = {c.db}.get({c.Res}, {c.idv})\n    o.total -= body.amount\n    {c.db}.commit()\n",
        )
        f = py_route(
            c,
            "POST",
            path,
            f"{c.idv}: int, body: Discount",
            f"    o = {c.db}.get({c.Res}, {c.idv})\n    if o.discount_applied or body.amount < 0 or body.amount > o.total:\n        raise Conflict()\n    o.total -= body.amount\n    o.discount_applied = True\n    {c.db}.commit()\n",
        )
        p = py_route(
            c,
            "POST",
            path,
            f"{c.idv}: int, body: Discount",
            f"    if body.amount < 0:\n        raise BadRequest()\n    o = {c.db}.get({c.Res}, {c.idv})\n    o.total -= body.amount\n    {c.db}.commit()\n",
        )
    return Sample(
        "bound_state_dependent",
        "CWE-1284",
        c.fw,
        v,
        f,
        p,
        "missing_check",
        "enforce_invariant",
        "WSTG-BUSL-01",
        "replaying the request applied the discount twice",
    )
