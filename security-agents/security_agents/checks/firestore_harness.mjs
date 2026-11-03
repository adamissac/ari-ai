// Reviewed Firestore-rules check harness (ADR-0023). Platform-owned, copied into the
// sandbox as `.sandbox/firestore_harness.mjs`; never generated, never model-authored.
//
//   node firestore_harness.mjs <params.json>
//
// Loads the workspace's own rules file into the run's Firestore emulator
// (FIRESTORE_EMULATOR_HOST) and records, for each operation in `ops`, whether the rules
// allowed it. The caller compares the outcomes with the expectation; this file decides
// nothing. Packages come from the platform directory ARI_NODE_DIR, not from the target.
import { readFileSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { join } from 'node:path';

const params = JSON.parse(readFileSync(process.argv[2], 'utf8'));
const require = createRequire(join(process.env.ARI_NODE_DIR, 'package.json'));
const { initializeTestEnvironment } = require('@firebase/rules-unit-testing');
const { doc, getDoc, setDoc, collection, getDocs, limit, query } = require('firebase/firestore');

const [host, port] = (process.env.FIRESTORE_EMULATOR_HOST || '').split(':');
if (host !== '127.0.0.1' && host !== 'localhost') throw new Error('emulator must be on loopback');

const env = await initializeTestEnvironment({
  projectId: params.project_id,
  firestore: { host, port: Number(port), rules: readFileSync(params.rules_path, 'utf8') },
});
const outcomes = [];
try {
  await env.clearFirestore();
  // Seed with rules disabled: the documents a real owner would already have.
  await env.withSecurityRulesDisabled(async (ctx) => {
    for (const s of params.seed) await setDoc(doc(ctx.firestore(), s.path), s.data);
  });
  for (const op of params.ops) {
    const db = (op.as === null ? env.unauthenticatedContext() : env.authenticatedContext(op.as, op.claims || {})).firestore();
    let allowed;
    let error = null;
    try {
      if (op.op === 'get') await getDoc(doc(db, op.path));
      else if (op.op === 'set') await setDoc(doc(db, op.path), op.data, { merge: true });
      else if (op.op === 'list') await getDocs(query(collection(db, op.path), limit(5)));
      else throw new Error(`unknown op ${op.op}`);
      allowed = true;
    } catch (e) {
      // Only a rules denial counts as "denied"; anything else is an error, not evidence.
      if (e && e.code === 'permission-denied') allowed = false;
      else { allowed = null; error = String(e && e.message || e).slice(0, 300); }
    }
    outcomes.push({ name: op.name, op: op.op, path: op.path, as: op.as, allowed, error });
  }
} finally {
  await env.cleanup();
}
writeFileSync(params.out, JSON.stringify({ outcomes }, null, 2));
