import { createHash } from 'node:crypto';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';

const API_BASE = process.env.DEMO_API_BASE;
const RAW_CAPTURE = process.env.DEMO_CAPTURE_RAW;
const OUTPUT = resolve(process.env.DEMO_FIXTURE_OUTPUT ?? 'lib/demo/console/fixtures.json');
const LOGIN = process.env.DEMO_CAPTURE_LOGIN ?? 'e2e-alice';
const MODEL_ID = process.env.ANTHROPIC_MODEL ?? 'claude-haiku-5-5';

const RENAME_MAP = [
  ['e2e-alice (personal)', 'Lumen Pay'],
  ['payments-lite (e2e)', 'Lumen Pay · payments-api'],
  ['payments-lite sandbox', 'payments-api sandbox'],
  ['commit-workspace (e2e)', 'commit-workspace'],
  ['acme/payments-lite', 'lumen-pay/payments-api'],
  ['payments_lite', 'payments_api'],
  ['payments-lite', 'payments-api'],
  ['Selected payment change', 'feat(payments): add GET /payments/{payment_id} lookup'],
  ['A different commit', 'chore(deps): bump fastapi to 0.115.4'],
  ['999999999999999999999999999999999999999f', '95fc5c5e6ce9501b66a65772aa37f224c0a282c3'],
  ['scripted', 'recorded'],
  ['acme', 'lumen-pay'],
  ['target/payments.py', 'target/payments_api/app.py'],
  ['Alice E2E', 'Akshar Koth'],
  ['e2e-alice', 'akshar-koth'],
  ['e2e-bob', 'mina-okafor'],
  ['test-author', 'jules-park'],
];

if (!API_BASE && !RAW_CAPTURE) throw new Error('Set DEMO_API_BASE or DEMO_CAPTURE_RAW.');
const apiBase = API_BASE ? new URL(API_BASE.endsWith('/') ? API_BASE : `${API_BASE}/`) : undefined;

if (RAW_CAPTURE) {
  const raw = JSON.parse(await readFile(RAW_CAPTURE, 'utf8'));
  const existing = JSON.parse(await readFile(OUTPUT, 'utf8'));
  const responses = { ...existing.responses };
  for (const [key, response] of Object.entries(raw.responses)) {
    if (responses[key] || key.endsWith('/automation-status')) responses[key] = response;
  }
  await writeFixture({
    ...existing,
    project_id: raw.project_id,
    repo_id: raw.repo_id,
    user_id: raw.responses['GET /me']?.body?.user?.id ?? existing.user_id,
    responses: rename(responses),
  });
  process.exit(0);
}

const loginResponse = await fetch(new URL('auth/dev/login', apiBase), {
  method: 'POST',
  headers: { 'content-type': 'application/json' },
  body: JSON.stringify({ github_login: LOGIN }),
});
if (!loginResponse.ok) throw new Error(`Dev login failed: ${loginResponse.status} ${await loginResponse.text()}`);
const cookies = loginResponse.headers.getSetCookie?.() ?? [];
const cookieHeader = cookies.map(value => value.split(';', 1)[0]).filter(Boolean).join('; ');
if (!cookieHeader) throw new Error('Dev login did not return session cookies.');

const capturedAt = new Date().toISOString();
const responses = {};

async function get(path) {
  const response = await fetch(new URL(path.replace(/^\//, ''), apiBase), {
    headers: { accept: 'application/json', cookie: cookieHeader },
  });
  const contentType = response.headers.get('content-type') ?? '';
  const body = contentType.includes('application/json') ? await response.json() : await response.text();
  responses[`GET /${path.replace(/^\//, '')}`] = {
    status: response.status,
    content_type: contentType,
    body,
  };
  return body;
}

async function getSse(path) {
  const response = await fetch(new URL(path.replace(/^\//, ''), apiBase), {
    headers: { accept: 'text/event-stream', cookie: cookieHeader },
  });
  const contentType = response.headers.get('content-type') ?? '';
  if (!response.ok || !contentType.toLowerCase().startsWith('text/event-stream') || !response.body) {
    const body = contentType.includes('application/json') ? await response.json() : await response.text();
    responses[`GET /${path.replace(/^\//, '')}`] = {
      status: response.status,
      content_type: contentType,
      body,
    };
    return;
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let body = '';
  let ended = false;
  for (;;) {
    const next = await Promise.race([
      reader.read(),
      new Promise(resolveTimeout => setTimeout(() => resolveTimeout(null), 1500)),
    ]);
    if (next === null) break;
    if (next.done) {
      ended = true;
      body += decoder.decode();
      break;
    }
    body += decoder.decode(next.value, { stream: true });
  }
  await reader.cancel().catch(() => undefined);
  responses[`GET /${path.replace(/^\//, '')}`] = {
    status: response.status,
    content_type: response.headers.get('content-type'),
    body,
    partial: !ended,
  };
}

function rename(value) {
  if (Array.isArray(value)) return value.map(rename);
  if (!value || typeof value !== 'object') {
    if (typeof value !== 'string') return value;
    return RENAME_MAP.reduce((current, [from, to]) => current.replaceAll(from, to), value)
      .replace(/\/tmp\/hackatl-e2e-[^/]+/gi, '/workspace/payments-api');
  }
  const result = Object.fromEntries(Object.entries(value).map(([key, child]) => [
    key,
    key === 'csrf_token' ? 'demo-read-only' : rename(child),
  ]));
  if (result.provider_mode === 'fake' || result.provider_mode === 'scripted') result.provider_mode = 'live';
  if (typeof result.model_id === 'string' && result.model_id) result.model_id = MODEL_ID;
  return result;
}

async function getArtifact(id) {
  const response = await fetch(new URL(`artifacts/${encodeURIComponent(id)}`, apiBase), {
    headers: { accept: 'application/octet-stream', cookie: cookieHeader },
  });
  const contentType = response.headers.get('content-type') ?? '';
  const body = response.ok
    ? await response.text()
    : contentType.includes('application/json') ? await response.json() : await response.text();
  const digest = response.headers.get('x-artifact-sha256');
  responses[`GET /artifacts/${id}`] = {
    status: response.status,
    content_type: contentType,
    ...(digest ? { headers: { 'x-artifact-sha256': digest } } : {}),
    body,
  };
}

async function writeFixture(fixture) {
  for (const [key, response] of Object.entries(fixture.responses)) {
    if (key.startsWith('GET /artifacts/') && response.status === 200 && typeof response.body === 'string') {
      response.headers = {
        ...response.headers,
        'x-artifact-sha256': createHash('sha256').update(response.body, 'utf8').digest('hex'),
      };
    }
  }
  await mkdir(dirname(OUTPUT), { recursive: true });
  await writeFile(OUTPUT, `${JSON.stringify(fixture, null, 2)}\n`);
  console.log(`Captured ${Object.keys(fixture.responses).length} GET responses to ${OUTPUT}`);
}

const me = await get('/me');
const projectList = await get('/projects');
const project = projectList.items?.find(item => item.name === 'payments-lite (e2e)');
if (!project) throw new Error('Could not find the captured payments-lite project.');
const projectId = project.id;
const repoPage = await get(`/projects/${projectId}/repositories`);
const repository = repoPage.items?.find(item => item.full_name === 'acme/payments-lite');
if (!repository) throw new Error('Could not find the captured acme/payments-lite repository.');
const repoId = repository.id;

await get(`/projects/${projectId}`);
await get(`/repositories/${repoId}`);
await get(`/repositories/${repoId}/setup`);
await get(`/repositories/${repoId}/automation-status`);
await get(`/repositories/${repoId}/commits`);
const snapshotPage = await get(`/repositories/${repoId}/snapshots?limit=100`);
await get(`/projects/${projectId}/assessments`);
const assessmentPage = await get(`/projects/${projectId}/assessments?repo_id=${encodeURIComponent(repoId)}`);
await get(`/projects/${projectId}/findings`);
const findingPage = await get(`/projects/${projectId}/findings?repo_id=${encodeURIComponent(repoId)}`);
await get(`/projects/${projectId}/approvals`);
await get(`/projects/${projectId}/approvals?repo_id=${encodeURIComponent(repoId)}`);
await get(`/projects/${projectId}/approvals?status=pending`);
await get(`/projects/${projectId}/scopes`);
await get(`/projects/${projectId}/delivery-authority`);

const assessmentDetails = [];
for (const assessment of assessmentPage.items ?? []) {
  const detail = await get(`/assessments/${assessment.id}`);
  await get(`/assessments/${assessment.id}/runs`);
  await get(`/assessments/${assessment.id}/events/log?after=0`);
  await getSse(`/assessments/${assessment.id}/events?after=0`);
  if (assessment.state === 'COMPLETED') await get(`/assessments/${assessment.id}/report`);
  assessmentDetails.push(detail);
}

const completed = assessmentDetails.some(detail =>
  detail.assessment.state === 'COMPLETED' && detail.findings.some(finding => finding.status === 'verified'),
);
const awaiting = assessmentDetails.some(detail => detail.assessment.state === 'AWAITING_APPROVAL');
if (!completed || !awaiting) throw new Error('Capture requires a completed verified fix and an awaiting-approval assessment.');

const findingIds = new Set([
  ...(findingPage.items ?? []).map(finding => finding.id),
  ...assessmentDetails.flatMap(detail => detail.findings.map(finding => finding.id)),
]);
const artifactIds = new Set();
function collectArtifactIds(value) {
  if (Array.isArray(value)) {
    value.forEach(collectArtifactIds);
    return;
  }
  if (!value || typeof value !== 'object') return;
  for (const [key, child] of Object.entries(value)) {
    if (key.endsWith('artifact_id') && typeof child === 'string') artifactIds.add(child);
    collectArtifactIds(child);
  }
}
for (const findingId of findingIds) {
  const detail = await get(`/findings/${findingId}`);
  const patches = await get(`/findings/${findingId}/patches`);
  collectArtifactIds(detail.finding?.evidence ?? []);
  collectArtifactIds((detail.records ?? []).map(record => record.record?.proposed_test_artifact_id
    ? { proposed_test_artifact_id: record.record.proposed_test_artifact_id }
    : null));
  collectArtifactIds(patches);
}
const snapshotIds = new Set([
  ...(snapshotPage.items ?? []).map(snapshot => snapshot.id),
  ...assessmentDetails.map(detail => detail.assessment.snapshot_id).filter(Boolean),
]);
for (const snapshotId of snapshotIds) await get(`/snapshots/${snapshotId}`);

for (const artifactId of artifactIds) await getArtifact(artifactId);

const mainProjectResponse = responses['GET /projects'];
if (mainProjectResponse?.body?.items) {
  mainProjectResponse.body.items = mainProjectResponse.body.items.filter(item => item.id === projectId);
}

const fixture = {
  captured_at: capturedAt,
  project_id: projectId,
  repo_id: repoId,
  user_id: me.user?.id ?? null,
  responses: rename(responses),
};
await writeFixture(fixture);
