import 'server-only';
import { Ajv2020 } from 'ajv/dist/2020.js';
import { createHash } from 'node:crypto';
import { readdir, readFile, stat } from 'node:fs/promises';
import path from 'node:path';
import type { BundleResponse, DefenseLabBundle } from './lab-types';

// Repository root (frontend/..). Only the RL results directory is ever read.
const ROOT = path.resolve(process.cwd(), '..');
const RESULTS = path.join(ROOT, 'rl-defense', 'results');
const SCHEMA = path.join(ROOT, 'rl-defense', 'fixtures', 'defense_lab.schema.json');
const PROTOCOL = /^protocol-v\d{1,3}$/;
const MAX_BYTES = 16 * 1024 * 1024;

let validator: ((value: unknown) => boolean) | undefined;
async function validate(value: unknown): Promise<boolean> {
  if (!validator) {
    // A missing or unreadable schema is a deployment problem; say so as JSON instead of a raw 500.
    let schema: object;
    try { schema = JSON.parse(await readFile(SCHEMA, 'utf8')) as object; }
    catch { throw new BundleError(500, 'Evaluation schema not available'); }
    validator = new Ajv2020({ strict: false, allErrors: false }).compile(schema);
  }
  return validator(value);
}

/** Committed evaluation runs that contain a Defense Lab bundle, newest protocol first. */
export async function listProtocols(): Promise<string[]> {
  const entries = await readdir(RESULTS, { withFileTypes: true }).catch(() => []);
  const found: string[] = [];
  for (const e of entries) {
    if (!e.isDirectory() || !PROTOCOL.test(e.name)) continue;
    if (await stat(path.join(RESULTS, e.name, 'defense_lab.json')).then(s => s.isFile(), () => false)) found.push(e.name);
  }
  return found.sort((a, b) => Number(b.slice(10)) - Number(a.slice(10)));
}

export class BundleError extends Error {
  constructor(readonly status: number, message: string) { super(message); }
}

export async function loadBundle(protocol: string): Promise<BundleResponse> {
  if (!PROTOCOL.test(protocol)) throw new BundleError(400, 'Invalid protocol name');
  const file = path.join(RESULTS, protocol, 'defense_lab.json');
  const info = await stat(file).catch(() => null);
  if (!info?.isFile()) throw new BundleError(404, `No defense_lab.json for ${protocol}`);
  if (info.size > MAX_BYTES) throw new BundleError(413, 'Bundle exceeds size limit');
  const bytes = await readFile(file);
  let value: unknown;
  try { value = JSON.parse(bytes.toString('utf8')); } catch { throw new BundleError(422, 'Bundle is not valid JSON'); }
  if (!(await validate(value))) throw new BundleError(422, 'Bundle does not match rl-defense/fixtures/defense_lab.schema.json');
  return {
    provenance: {
      protocol,
      path: path.relative(ROOT, file),
      sha256: createHash('sha256').update(bytes).digest('hex'),
      bytes: info.size,
      schemaPath: path.relative(ROOT, SCHEMA),
    },
    bundle: value as DefenseLabBundle,
  };
}
