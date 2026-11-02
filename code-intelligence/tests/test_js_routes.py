from pathlib import Path

from intel_test_helpers import commit
from intel_test_helpers import repository as repository
from shared.intelligence import SnapshotRef

from code_intelligence.ingest import GitReader
from code_intelligence.js_routes import JsRouteExtractor

REF = SnapshotRef(
    project_id="prj_00000000",
    repo_id="rep_00000000",
    snapshot_id="snp_00000000",
    commit_sha="a" * 40,
    index_version="test",
)

SOURCES = {
    # Next.js App Router: exported verbs only; `runtime` is not a route.
    "src/app/api/users/[id]/route.ts": (
        'export const runtime = "nodejs";\n'
        "export async function GET(req: Request) {\n"
        "  const h = req.headers.get('authorization');\n"
        "  return Response.json({ h });\n"
        "}\n"
        "const remove = async () => new Response(null);\n"
        "export { remove as DELETE };\n"
    ),
    "app/(marketing)/docs/[...slug]/route.js": "export const POST = () => new Response('');\n",
    # Pages API and Vercel functions: methods from req.method comparisons.
    "pages/api/items/index.ts": (
        "export default function handler(req, res) {\n"
        "  if (req.method === 'POST') return res.status(201).end();\n"
        "  if (req.method !== 'GET') return res.status(405).end();\n"
        "  return res.json([]);\n"
        "}\n"
    ),
    "api/verify.js": ("import { make } from '../server/make.js';\nexport default make();\n"),
    "api/_helpers.js": "export default function x() {}\n",
    # Express, including a non-literal path that must be flagged.
    "server/app.js": (
        "const express = require('express');\n"
        "const app = express();\n"
        "const router = express.Router();\n"
        "router.get('/orders/:orderId', (req, res) => res.json({}));\n"
        "app.post('/login', async (req, res) => { await admin.auth().verifyIdToken(t); });\n"
        "app.get(PATH, (req, res) => res.end());\n"
        "app.use('/api', router);\n"
    ),
    # Cloud Functions (v2 import style and v1 namespace style).
    "functions/index.js": (
        "const { onRequest } = require('firebase-functions/v2/https');\n"
        "exports.health = onRequest((req, res) => res.send('ok'));\n"
    ),
    "functions/src/main.ts": (
        "import * as functions from 'firebase-functions';\n"
        "export const report = functions.https.onRequest(async (req, res) => { res.end(); });\n"
    ),
    # Not routes: a plain module mentioning "expression", and a test file.
    "src/lib/math.ts": "export const expression = (a: number) => a + 1;\n",
    "app/api/x/route.test.ts": "export function GET() {}\n",
}


def test_js_ts_routes_follow_each_convention(repository: tuple[Path, str]) -> None:
    path, _ = repository
    for rel, content in SOURCES.items():
        (path / rel).parent.mkdir(parents=True, exist_ok=True)
        (path / rel).write_text(content)
    sha = commit(path)
    _, files, _ = GitReader(path).read(sha)
    extractor = JsRouteExtractor(REF, files)
    extractor.extract()
    symbols = {s.id: s for s in extractor.symbols}
    routes = {
        (e.method, e.path_template): (symbols[e.handler_symbol_id].path, e.auth_dependencies)
        for e in extractor.entries
    }
    assert routes == {
        ("GET", "/api/users/{id}"): ("src/app/api/users/[id]/route.ts", ["authorization"]),
        ("DELETE", "/api/users/{id}"): ("src/app/api/users/[id]/route.ts", []),
        ("POST", "/docs/{slug}"): ("app/(marketing)/docs/[...slug]/route.js", []),
        ("GET", "/api/items"): ("pages/api/items/index.ts", []),
        ("POST", "/api/items"): ("pages/api/items/index.ts", []),
        ("ANY", "/api/verify"): ("api/verify.js", []),
        ("GET", "/orders/{orderId}"): ("server/app.js", []),
        ("POST", "/login"): ("server/app.js", ["verifyIdToken"]),
        ("ANY", "/health"): ("functions/index.js", []),
        ("ANY", "/report"): ("functions/src/main.ts", []),
    }
    assert [(i.path, i.reason) for i in extractor.issues] == [
        ("server/app.js", "non-literal Express path at line 6")
    ]
    # Every entry point references an emitted symbol, and ids are deterministic.
    again = JsRouteExtractor(REF, files)
    again.extract()
    assert [e.id for e in again.entries] == [e.id for e in extractor.entries]
