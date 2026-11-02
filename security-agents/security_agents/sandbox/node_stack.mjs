// Platform-owned Node target launcher (ADR-0023). Runs inside the sandbox, cwd = the
// target workspace. Never generated, never model-authored; its only input is a config
// the platform derived from the validated node_http recipe.
//
//   node node_stack.mjs <config.json>
//
// 1. starts the Firebase Auth / Firestore emulators on loopback (platform firebase-tools),
// 2. creates the recipe's fixture identities and seed documents in them,
// 3. serves the app on 127.0.0.1:<app port> through a fixed adapter,
// then prints `@@ARI_READY@@` and stays up until killed.
import { spawn } from 'node:child_process';
import { generateKeyPairSync } from 'node:crypto';
import { existsSync, mkdtempSync, readdirSync, readFileSync, writeFileSync } from 'node:fs';
import { createServer } from 'node:http';
import { createConnection } from 'node:net';
import { createRequire } from 'node:module';
import { tmpdir } from 'node:os';
import { join, resolve, sep } from 'node:path';
import { pathToFileURL } from 'node:url';

const cfg = JSON.parse(readFileSync(process.argv[2], 'utf8'));
const HOST = '127.0.0.1';
const WORK = process.cwd();
const platform = createRequire(join(cfg.node_dir, 'package.json'));

function log(...a) { process.stderr.write(`[node_stack] ${a.join(' ')}\n`); }

async function waitPort(port, ms = 90_000) {
  const end = Date.now() + ms;
  for (;;) {
    const ok = await new Promise((r) => {
      const s = createConnection({ host: HOST, port }, () => { s.end(); r(true); });
      s.on('error', () => r(false));
    });
    if (ok) return;
    if (Date.now() > end) throw new Error(`port ${port} did not open`);
    await new Promise((r) => setTimeout(r, 250));
  }
}

// ---------------------------------------------------------------- emulators
async function startEmulators() {
  const only = cfg.emulators;
  if (!only.length) return;
  const dir = mkdtempSync(join(tmpdir(), 'ari-fb-'));
  const emulators = { ui: { enabled: false }, hub: { host: HOST, port: cfg.ports.hub },
    logging: { host: HOST, port: cfg.ports.logging } };
  for (const name of only) emulators[name] = { host: HOST, port: cfg.ports[name] };
  if (emulators.firestore) emulators.firestore.websocketPort = cfg.ports.ws;
  writeFileSync(join(dir, 'firebase.json'), JSON.stringify({ emulators }));
  const bin = join(cfg.node_dir, 'node_modules', 'firebase-tools', 'lib', 'bin', 'firebase.js');
  const child = spawn(process.execPath, [bin, 'emulators:start', '--only', only.join(','),
    '--project', cfg.project_id, '--config', join(dir, 'firebase.json')], {
    cwd: dir, stdio: ['ignore', 'pipe', 'pipe'],
    env: { ...process.env, HOME: dir, FIREBASE_CLI_DISABLE_UPDATE_CHECK: 'true', NO_UPDATE_NOTIFIER: '1' },
  });
  child.stdout.on('data', (d) => process.stderr.write(d));
  child.stderr.on('data', (d) => process.stderr.write(d));
  process.on('exit', () => child.kill('SIGKILL'));
  await Promise.all(only.map((n) => waitPort(cfg.ports[n])));
  log('emulators up:', only.join(','));
}

async function seed() {
  if (cfg.emulators.includes('auth')) {
    for (const id of cfg.identities) {
      const r = await fetch(`http://${HOST}:${cfg.ports.auth}/identitytoolkit.googleapis.com/v1/projects/${cfg.project_id}/accounts`, {
        method: 'POST', headers: { 'content-type': 'application/json', authorization: 'Bearer owner' },
        body: JSON.stringify({ localId: id.uid, email: id.email || undefined, emailVerified: !!id.email_verified,
          customAttributes: JSON.stringify(id.claims || {}) }),
      });
      if (!r.ok) throw new Error(`seeding identity ${id.uid}: ${r.status}`);
    }
  }
  if (cfg.emulators.includes('firestore') && cfg.seed.length) {
    const { initializeTestEnvironment } = platform('@firebase/rules-unit-testing');
    const { doc, setDoc } = platform('firebase/firestore');
    const env = await initializeTestEnvironment({ projectId: cfg.project_id,
      firestore: { host: HOST, port: cfg.ports.firestore } });
    await env.withSecurityRulesDisabled(async (ctx) => {
      for (const s of cfg.seed) await setDoc(doc(ctx.firestore(), s.path), s.data);
    });
    await env.cleanup();
  }
  log('seeded', cfg.identities.length, 'identities,', cfg.seed.length, 'documents');
}

// ---------------------------------------------------------------- app environment
function appEnv() {
  const out = {};
  for (const [k, v] of Object.entries(cfg.env)) {
    if (v === '$sandbox_service_account') {
      // Throwaway per run. With the emulator variables set, firebase-admin never calls Google.
      const { privateKey } = generateKeyPairSync('rsa', { modulusLength: 2048 });
      out[k] = JSON.stringify({ type: 'service_account', project_id: cfg.project_id,
        client_email: `ari-sandbox@${cfg.project_id}.iam.gserviceaccount.com`,
        private_key: privateKey.export({ type: 'pkcs8', format: 'pem' }) });
    } else out[k] = v;
  }
  if (cfg.emulators.includes('auth')) out.FIREBASE_AUTH_EMULATOR_HOST = `${HOST}:${cfg.ports.auth}`;
  if (cfg.emulators.includes('firestore')) out.FIRESTORE_EMULATOR_HOST = `${HOST}:${cfg.ports.firestore}`;
  out.GCLOUD_PROJECT = out.GOOGLE_CLOUD_PROJECT = cfg.project_id;
  return out;
}

// ---------------------------------------------------------------- vercel_functions adapter
const EXT = ['.js', '.mjs', '.cjs'];

function resolveFunction(root, parts) {
  // Static file first, then index, then one dynamic `[param]` segment per level.
  let dir = root;
  const query = {};
  for (let i = 0; i < parts.length; i++) {
    const last = i === parts.length - 1;
    const part = parts[i];
    if (last) {
      for (const e of EXT) if (existsSync(join(dir, part + e))) return { file: join(dir, part + e), query };
      for (const e of EXT) if (existsSync(join(dir, part, 'index' + e))) return { file: join(dir, part, 'index' + e), query };
    } else if (existsSync(join(dir, part))) { dir = join(dir, part); continue; }
    const dyn = (existsSync(dir) ? readdirSync(dir) : []).find((n) => /^\[[A-Za-z_][A-Za-z0-9_]*\](\.[cm]?js)?$/.test(n)
      && (last ? EXT.some((e) => n.endsWith(e)) : !EXT.some((e) => n.endsWith(e))));
    if (!dyn) return null;
    query[dyn.replace(/^\[|\](\.[cm]?js)?$/g, '')] = decodeURIComponent(part);
    if (last) return { file: join(dir, dyn), query };
    dir = join(dir, dyn);
  }
  for (const e of EXT) if (existsSync(join(dir, 'index' + e))) return { file: join(dir, 'index' + e), query };
  return null;
}

async function readBody(req) {
  const chunks = [];
  let size = 0;
  for await (const c of req) { size += c.length; if (size > 1_000_000) throw new Error('body too large'); chunks.push(c); }
  const raw = Buffer.concat(chunks).toString('utf8');
  const type = (req.headers['content-type'] || '').split(';')[0].trim();
  if (!raw) return undefined;
  if (type === 'application/json') { try { return JSON.parse(raw); } catch { return raw; } }
  if (type === 'application/x-www-form-urlencoded') return Object.fromEntries(new URLSearchParams(raw));
  return raw;
}

function vercelResponse(res) {
  res.status = (c) => { res.statusCode = c; return res; };
  res.json = (o) => { if (!res.getHeader('content-type')) res.setHeader('content-type', 'application/json; charset=utf-8'); res.end(JSON.stringify(o)); return res; };
  res.send = (b) => { if (typeof b === 'object' && !Buffer.isBuffer(b)) return res.json(b); res.end(b); return res; };
  res.redirect = (a, b) => { const [c, u] = typeof a === 'number' ? [a, b] : [307, a]; res.statusCode = c; res.setHeader('location', u); res.end(); return res; };
  return res;
}

async function serveVercel(port) {
  const root = resolve(WORK, cfg.serve.dir || 'api');
  const server = createServer(async (req, res) => {
    vercelResponse(res);
    // Same access-log shape as uvicorn, so the platform's target_contact evidence parses it.
    res.on('finish', () => log(`"${req.method} ${req.url} HTTP/1.1" ${res.statusCode}`));
    try {
      const url = new URL(req.url, `http://${HOST}`);
      if (url.pathname === '/') return res.status(200).json({ ari_sandbox: true });
      const parts = url.pathname.split('/').filter(Boolean);
      if (parts[0] !== (cfg.serve.dir || 'api') || parts.some((p) => p.startsWith('.') || p.startsWith('_'))) return res.status(404).json({ error: 'not found' });
      const found = resolveFunction(root, parts.slice(1));
      if (!found || !resolve(found.file).startsWith(root + sep)) return res.status(404).json({ error: 'not found' });
      const mod = await import(pathToFileURL(found.file).href);
      const handler = mod.default?.default || mod.default;
      if (typeof handler !== 'function') return res.status(500).json({ error: 'no default export' });
      req.query = { ...Object.fromEntries(url.searchParams), ...found.query };
      req.cookies = Object.fromEntries((req.headers.cookie || '').split(';').filter(Boolean).map((c) => c.trim().split('=')));
      req.body = await readBody(req);
      await handler(req, res);
    } catch (e) {
      log('handler error:', e?.stack || e);
      if (!res.headersSent) res.status(500).json({ error: 'handler error' });
    }
  });
  await new Promise((r) => server.listen(port, HOST, r));
}

// ---------------------------------------------------------------- main
await startEmulators();
await seed();
Object.assign(process.env, appEnv());
if (cfg.serve) {
  if (cfg.serve.adapter !== 'vercel_functions') throw new Error(`adapter ${cfg.serve.adapter} is not implemented yet`);
  await serveVercel(cfg.ports.app);
}
process.stdout.write('@@ARI_READY@@\n');
setInterval(() => {}, 1 << 30);
