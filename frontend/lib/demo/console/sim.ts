import fixtures from './fixtures.json';
import { DEMO_GITHUB_REPOS, DEMO_SIM_STORAGE_KEY as STORAGE_KEY } from './state';

/**
 * The demo account's simulated backend (ADR-0024). The recorded fixtures are the read-only
 * history; this layer lets a visitor walk the real console flow on top of them, entirely in
 * this browser tab: choose a fictional Lumen Pay repository, connect it, answer setup, approve
 * a sandbox scope, start a check and approve the fix. A started check replays the recorded
 * assessment on a compressed clock. Nothing reaches GitHub or the Ari backend; state lives in
 * sessionStorage and is cleared on sign-in and on exit.
 */

type Json = Record<string, unknown>;
type Fixture = (key: string) => unknown;

const PROJECT = fixtures.project_id;
const REPO = fixtures.repo_id;
const USER = fixtures.user_id;
const INSTALLATION = 4242;
/** The recorded full run: review, seven agents, approval, patch, verify. Replays copy it. */
const TEMPLATE = 'asm_01M6FV2SMWPFS8PH97GT8X4FB2';
/** A second recording paused at approval; the seeded replay (-r0) takes its place. */
const HIDDEN = 'asm_01M6FV677W708K04TE8Y7JHV29';
/** Event after which a full replay waits for the visitor's approval. */
const PAUSE_SEQ = 35;
/** Recorded events that end a run: REPORTING, COMPLETED, assessment.completed. */
const ENDING = [61, 63, 64];
/** A clean run: setup, functional review and Scout's recon, then the report. */
const CLEAN = [1, 2, 3, 4, 5, 6, 7, 8, 9, 27, ...ENDING];
export const REPLAY_PACE_MS = 1400;

interface Run {
  id: string;
  kind: 'full' | 'clean';
  repoId: string;
  sha: string;
  scopeId: string;
  startedAt: number;
  decidedAt: number | null;
  declined: boolean;
}

interface SimState {
  repos: Json[];
  auto: Record<string, boolean>;
  setups: Record<string, Json>;
  settings: Json | null;
  scopes: Json[];
  approvals: Json[];
  decisions: Record<string, { status: 'approved' | 'declined'; reason: string | null; at: number }>;
  runs: Run[];
  counter: number;
}

const iso = (time: number) => new Date(time).toISOString();
const clone = <T>(value: T): T => JSON.parse(JSON.stringify(value)) as T;
const raw = (key: string) => clone((fixtures.responses as Record<string, { body: unknown }>)[key]?.body);
const recorded = raw(`GET /assessments/${TEMPLATE}`) as { assessment: Json; agent_runs: Json[]; findings: Json[] };
const recordedEvents = (raw(`GET /assessments/${TEMPLATE}/events/log?after=0`) as { items: Json[] }).items;
const recordedSha = recorded.assessment.commit_sha as string;
const recordedScope = recorded.assessment.scope_id as string;
const hiddenDetail = raw(`GET /assessments/${HIDDEN}`) as { findings: Json[] } | undefined;
const hiddenEvents = (raw(`GET /assessments/${HIDDEN}/events/log?after=0`) as { items: Json[] } | undefined)?.items ?? [];
/** Records of the paused recording that the seeded replay stands in for; the account never serves them. */
export const HIDDEN_IDS = new Set<string>([
  HIDDEN,
  ...(hiddenDetail?.findings ?? []).map(f => f.id as string),
  ...hiddenEvents.map(e => e.approval_id as string | null).filter((id): id is string => !!id),
]);
/** What a fix approval asks, by subject kind; the recorded run's own text was overwritten when it was approved. */
const REQUEST_REASON = new Map(((raw(`GET /projects/${PROJECT}/approvals`) as { items: Json[] }).items)
  .filter(a => HIDDEN_IDS.has(a.id as string))
  .map(a => [String(a.subject_id).slice(0, 4), a.reason as string | null]));
const SETUP_DONE = { readiness: true, strictness: '2', reviewChanges: true, comments: true, watch: false, scope: true, delivery: 'manual', reviewStart: true };

function initial(now: number): SimState {
  return {
    repos: [],
    auto: {},
    setups: {},
    settings: null,
    scopes: [],
    approvals: [],
    decisions: {},
    // The account opens with one check paused for a human decision, as a real one would be.
    runs: [{ id: `${TEMPLATE}-r0`, kind: 'full', repoId: REPO, sha: recordedSha, scopeId: recordedScope, startedAt: now - 5 * 60_000, decidedAt: null, declined: false }],
    counter: 0,
  };
}

/** Used only when sessionStorage is unavailable; otherwise storage is the single source. */
let memory: SimState | null = null;

function load(now: number): SimState {
  try {
    const stored = globalThis.sessionStorage?.getItem(STORAGE_KEY);
    if (stored) return JSON.parse(stored) as SimState;
    if (globalThis.sessionStorage) {
      const fresh = initial(now);
      globalThis.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(fresh));
      return fresh;
    }
  } catch { /* storage unavailable: keep the state in memory */ }
  return (memory ??= initial(now));
}

function save(state: SimState): void {
  memory = state;
  try { globalThis.sessionStorage?.setItem(STORAGE_KEY, JSON.stringify(state)); } catch { /* memory only */ }
}

// ------------------------------------------------------------------ replays

const RECORD_ID = /\b(asm|fnd|run|apv|rmp|hdn|ver|pat|val)_([0-9A-Z]{26})(?![0-9A-Za-z_-])/g;
const TIMESTAMP = /\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})\b/g;

function deepMap(value: unknown, map: (text: string) => string): unknown {
  if (Array.isArray(value)) return value.map(item => deepMap(item, map));
  if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).map(([k, v]) => [k, deepMap(v, map)]));
  return typeof value === 'string' ? map(value) : value;
}

function suffixOf(run: Run): string {
  return run.id.slice(TEMPLATE.length + 1);
}

/** Copy a recorded record into a replay: its own ids, repository and commit. */
function rekey(run: Run, value: unknown): unknown {
  const suffix = suffixOf(run);
  return deepMap(value, text => {
    if (text === REPO) return run.repoId;
    if (text === recordedSha) return run.sha;
    if (text === recordedScope) return run.scopeId;
    return text.replace(RECORD_ID, (_, prefix: string, id: string) => `${prefix}_${id}-${suffix}`);
  });
}

function baseId(id: string): string {
  return id.replace(/-(?:r|c)\d+$/, '');
}

interface Timeline { events: Json[]; visibleAt: number[]; visible: number; paused: boolean; done: boolean }

function timeline(run: Run, now: number): Timeline {
  const bySeq = new Map(recordedEvents.map(e => [e.seq as number, e]));
  let picks: number[];
  if (run.kind === 'clean') picks = CLEAN;
  else if (run.decidedAt === null) picks = recordedEvents.map(e => e.seq as number).filter(seq => seq <= PAUSE_SEQ);
  else if (run.declined) picks = [...recordedEvents.map(e => e.seq as number).filter(seq => seq <= PAUSE_SEQ), ...ENDING];
  else picks = recordedEvents.map(e => e.seq as number);
  const events = picks.map((seq, index) => {
    const event = rekey(run, bySeq.get(seq)) as Json;
    return { ...event, seq: index + 1 } as Json;
  });
  const visibleAt = picks.map((seq, index) => {
    if (run.kind === 'full' && seq > PAUSE_SEQ && run.decidedAt !== null) {
      const first = picks.findIndex(s => s > PAUSE_SEQ);
      // The first two (checkpoint consumed, state -> REMEDIATION) land at the decision itself:
      // the page stops polling while it shows AWAITING_APPROVAL in the demo account.
      return run.decidedAt + Math.max(0, index - first - 1) * REPLAY_PACE_MS;
    }
    return run.startedAt + 400 + index * REPLAY_PACE_MS;
  });
  const visible = visibleAt.filter(at => at <= now).length;
  const done = visible === events.length && events.at(-1)?.type === 'assessment.completed';
  return { events, visibleAt, visible, paused: !done && visible === events.length, done };
}

/** Map recorded times onto the replay clock, so each record is dated when it appeared. */
function retime(run: Run, line: Timeline, value: unknown): unknown {
  const points = line.events.map((e, i) => [Date.parse(e.at as string), line.visibleAt[i]!] as const)
    .sort((a, b) => a[0] - b[0]);
  const wall = (time: number): number => {
    if (points.length === 0) return run.startedAt;
    if (time <= points[0]![0]) return points[0]![1] - (points[0]![0] - time);
    for (let i = 1; i < points.length; i++) {
      const [t0, w0] = points[i - 1]!;
      const [t1, w1] = points[i]!;
      if (time <= t1) return t1 === t0 ? w1 : w0 + ((time - t0) / (t1 - t0)) * (w1 - w0);
    }
    return points.at(-1)![1] + (time - points.at(-1)![0]);
  };
  return deepMap(value, text => text.replace(TIMESTAMP, stamp => {
    const time = Date.parse(stamp);
    return Number.isNaN(time) ? stamp : iso(wall(time));
  }));
}

interface Slice { assessment: Json; agent_runs: Json[]; findings: Json[]; events: Json[]; line: Timeline }

function slice(run: Run, now: number): Slice {
  const line = timeline(run, now);
  const shown = line.events.slice(0, line.visible);
  const startedRuns = new Set(shown.filter(e => e.type === 'agent_run.started').map(e => e.agent_run_id as string));
  const finishedRuns = new Set(shown.filter(e => e.type === 'agent_run.finished').map(e => e.agent_run_id as string));
  const status = new Map<string, string>();
  for (const e of shown) {
    const data = e.data as Json;
    if (e.finding_id && typeof data.status === 'string' && !data.classification_only) status.set(e.finding_id as string, data.status);
  }
  const lastState = [...shown].reverse().find(e => e.type === 'assessment.state_changed')?.state as string | undefined;
  const last = shown.at(-1);
  const detail = rekey(run, recorded) as { assessment: Json; agent_runs: Json[]; findings: Json[] };
  const assessment: Json = {
    ...detail.assessment,
    state: lastState ?? 'CREATED',
    created_by: USER,
    updated_at: last?.at ?? detail.assessment.created_at,
    completed_at: line.done ? last?.at ?? null : null,
  };
  if (run.kind === 'clean') assessment.snapshot_id = null;
  const agentRuns = detail.agent_runs
    .filter(r => startedRuns.has(r.id as string))
    .map(r => finishedRuns.has(r.id as string) ? r : { ...r, status: 'running', ended_at: null });
  const findings = detail.findings
    .filter(f => status.has(f.id as string))
    .map(f => {
      const history = Array.isArray(f.history) ? (f.history as Json[]).filter(h => typeof h.at !== 'string' || h.at <= (last?.at as string)) : f.history;
      return { ...f, status: status.get(f.id as string), history };
    });
  return { ...(retime(run, line, { assessment, agent_runs: agentRuns, findings, events: shown }) as Omit<Slice, 'line'>), line };
}

function sse(run: Run, after: number, signal: AbortSignal | null | undefined): Response {
  const encoder = new TextEncoder();
  let sent = after;
  let timer: ReturnType<typeof setInterval> | undefined;
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(encoder.encode('retry: 2000\n\n'));
      const push = () => {
        const current = slice(run, Date.now());
        for (const event of current.events) {
          if ((event.seq as number) <= sent) continue;
          sent = event.seq as number;
          controller.enqueue(encoder.encode(`id: ${sent}\nevent: ${event.type as string}\ndata: ${JSON.stringify(event)}\n\n`));
        }
        // Close once nothing more can arrive without the visitor (end of run, or the approval gate).
        if (sent >= current.events.length && (current.line.done || current.line.paused)) {
          if (timer) clearInterval(timer);
          controller.close();
        }
      };
      push();
      timer = setInterval(() => {
        try { run = findRun(run.id) ?? run; push(); } catch { if (timer) clearInterval(timer); }
      }, 250);
      signal?.addEventListener('abort', () => { if (timer) clearInterval(timer); try { controller.close(); } catch { /* closed */ } });
    },
    cancel() { if (timer) clearInterval(timer); },
  });
  return new Response(body, { status: 200, headers: { 'content-type': 'text/event-stream; charset=utf-8' } });
}

function findRun(id: string): Run | undefined {
  return load(Date.now()).runs.find(run => run.id === id);
}

function runOf(id: string, state: SimState): Run | undefined {
  return state.runs.find(run => run.id === id);
}

/** The run a replayed record belongs to, from its id suffix. */
function runForRecord(id: string, state: SimState): Run | undefined {
  const match = /-((?:r|c)\d+)$/.exec(id);
  return match ? state.runs.find(run => run.id === `${TEMPLATE}-${match[1]}`) : undefined;
}

function runApprovals(run: Run, state: SimState, now: number): Json[] {
  if (run.kind !== 'full') return [];
  const current = slice(run, now);
  const requested = new Set(current.events.filter(e => e.type === 'approval.requested').map(e => e.approval_id as string));
  const all = (raw(`GET /projects/${PROJECT}/approvals`) as { items: Json[] }).items;
  return (rekey(run, all.filter(a => requested.has(rekey(run, a.id) as string))) as Json[])
    .map(a => {
      const event = current.events.find(e => e.approval_id === a.id);
      const decision = state.decisions[a.id as string];
      return {
        ...a,
        requested_at: event?.at ?? a.requested_at,
        status: decision?.status ?? 'pending',
        decided_at: decision ? iso(decision.at) : null,
        decided_by: decision ? USER : null,
        reason: decision ? decision.reason : REQUEST_REASON.get(String(a.subject_id).slice(0, 4)) ?? null,
      };
    });
}

// ------------------------------------------------------------------ helpers

function json(body: unknown, status = 200): Response {
  return new Response(body === null ? null : JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });
}

function error(status: number, code: string, message: string): Response {
  return json({ error: { code, message, details: {}, request_id: null } }, status);
}

function page(items: unknown[]): Json {
  return { items, next_cursor: null };
}

function demoRepoFor(fullName: string) {
  return DEMO_GITHUB_REPOS.find(repo => `${repo.org}/${repo.name}` === fullName);
}

function settingsOf(state: SimState, fixture: Fixture): Json {
  return state.settings ?? ((fixture(`GET /projects/${PROJECT}`) as Json).settings as Json);
}

function project(state: SimState, fixture: Fixture): Json {
  return { ...(fixture(`GET /projects/${PROJECT}`) as Json), name: 'Lumen Pay', settings: settingsOf(state, fixture) };
}

function repositories(state: SimState, fixture: Fixture): Json[] {
  const recordedRepos = (fixture(`GET /projects/${PROJECT}/repositories`) as { items: Json[] }).items;
  return [...recordedRepos, ...state.repos].map(repo => ({ ...repo, automatic_assessments: state.auto[repo.id as string] ?? repo.automatic_assessments }));
}

function scopes(state: SimState, fixture: Fixture, now: number): Json[] {
  const recordedScopes = (fixture(`GET /projects/${PROJECT}/scopes`) as { items: Json[] }).items;
  return [...recordedScopes, ...state.scopes].map(scope => (
    scope.status === 'active' && Date.parse(scope.expires_at as string) < now ? { ...scope, status: 'expired' } : scope
  ));
}

function activeScopeFor(repoId: string, state: SimState, fixture: Fixture, now: number): Json | undefined {
  return scopes(state, fixture, now).find(scope => scope.status === 'active'
    && (scope.targets as Json[]).some(target => target.repo_id === repoId));
}

function commitsFor(repoId: string, state: SimState, now: number, fixture: Fixture): Json | undefined {
  if (repoId === REPO) {
    const body = fixture(`GET /repositories/${REPO}/commits`) as { items: Json[] };
    // No link out to a GitHub page: the organization and commits are fictional.
    // Recent pushes, newest first; no link out to a GitHub page (the organization is fictional).
    return { ...body, items: body.items.map((item, i) => ({ ...item, committed_at: iso(now - (i === 0 ? 70 : 26 * 60) * 60_000), html_url: null })) };
  }
  const repo = state.repos.find(r => r.id === repoId);
  const source = repo && demoRepoFor(repo.full_name as string);
  if (!source) return undefined;
  return {
    items: source.commits.map(commit => ({ sha: commit.sha, message: commit.message, author: commit.author, committed_at: iso(now - commit.minutesAgo * 60_000), html_url: null })),
    next_cursor: null,
    available: true,
    reason: null,
  };
}

function runAssessments(state: SimState, now: number, repoId: string | null): Json[] {
  return state.runs.filter(run => !repoId || run.repoId === repoId).map(run => slice(run, now).assessment);
}

function byNewest(items: Json[]): Json[] {
  return [...items].sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)));
}

function automation(repoId: string, state: SimState, fixture: Fixture, now: number): Json {
  const repo = repositories(state, fixture).find(r => r.id === repoId);
  const monitoring = (settingsOf(state, fixture).monitoring_policy as Json).enabled === true;
  const reasons: Json[] = [];
  if (!repo?.automatic_assessments) reasons.push({ code: 'repository_off', message: 'Automatic reviews are off for this repository.' });
  if (!monitoring) reasons.push({ code: 'project_monitoring_off', message: 'Project monitoring is off.' });
  const off = reasons.length > 0;
  if (!activeScopeFor(repoId, state, fixture, now)) reasons.push({ code: 'scope_missing', message: 'No approved sandbox scope covers this repository.' });
  return { repo_id: repoId, state: off ? 'off' : reasons.length ? 'blocked' : 'ready', reasons, resets_at: null };
}

// ------------------------------------------------------------------ routes

/**
 * Answer one request from the simulated account, or return undefined to fall through to
 * the recorded fixtures. `fixture` returns a recorded body already moved to today's dates.
 */
export function simulate(method: string, path: string, query: URLSearchParams, body: unknown, fixture: Fixture, signal?: AbortSignal | null): Response | undefined {
  const now = Date.now();
  const state = load(now);
  const input = (body && typeof body === 'object' ? body : {}) as Json;
  const parts = path.split('/').filter(Boolean);
  const repoParam = query.get('repo_id');

  if (method === 'GET') {
    if (path === '/projects') {
      // Only the sample company's project; capture leftovers are not part of the account.
      return json(page([project(state, fixture)]));
    }
    if (path === `/projects/${PROJECT}`) return json(project(state, fixture));
    if (path === '/github/repositories') {
      const connected = repositories(state, fixture);
      return json({
        items: DEMO_GITHUB_REPOS.map(repo => {
          const fullName = `${repo.org}/${repo.name}`;
          const row = connected.find(r => r.full_name === fullName);
          return { full_name: fullName, installation_id: INSTALLATION, default_branch: repo.defaultBranch, private: repo.visibility !== 'public', connected_repo_id: (row?.id as string | undefined) ?? null, disconnected: false };
        }),
        // No link to the real GitHub App install page from the demo account.
        install_url: null,
        live_checked: true,
        next_cursor: null,
      });
    }
    if (path === `/projects/${PROJECT}/repositories`) return json(page(repositories(state, fixture)));
    if (parts[0] === 'repositories' && parts[1]) {
      const repoId = parts[1];
      const repo = repositories(state, fixture).find(r => r.id === repoId);
      if (!repo) return undefined;
      if (parts.length === 2) return json(repo);
      if (parts[2] === 'setup' && parts.length === 3) {
        const saved = state.setups[repoId];
        if (saved) return json(saved);
        if (repoId === REPO) return json({ repo_id: REPO, answers: SETUP_DONE, complete: true, completed_at: iso(now - 9 * 86_400_000), updated_at: iso(now - 9 * 86_400_000) });
        return json({ repo_id: repoId, answers: Object.fromEntries(Object.keys(SETUP_DONE).map(key => [key, null])), complete: false, completed_at: null, updated_at: null });
      }
      if (parts[2] === 'commits') return json(commitsFor(repoId, state, now, fixture));
      if (parts[2] === 'automation-status') return json(automation(repoId, state, fixture, now));
      if (parts[2] === 'snapshots' && repoId !== REPO) return json(page([]));
      return undefined;
    }
    if (path === '/audit' && query.get('project_id') === PROJECT) {
      // Build-recipe outcomes: payments-api already ships one; a newly connected repository
      // gets the build-recipe pull request a real connect opens (no link: GitHub is not used).
      const recipe = [
        { action: 'recipe.skipped', subject_id: REPO, at: iso(now - 10 * 86_400_000), details: { reason: 'build_recipe.json is already on the default branch.' } },
        ...state.repos.map(repo => ({ action: 'recipe.pr_opened', subject_id: repo.id, at: iso(Date.parse(repo.created_at as string) + 4000), details: { branch: 'ari/build-recipe' } })),
      ];
      return json({ items: recipe.reverse(), next_cursor: null });
    }
    if (path === `/projects/${PROJECT}/scopes`) return json(page(scopes(state, fixture, now)));
    if (path === `/projects/${PROJECT}/delivery-authority`) {
      const mode = settingsOf(state, fixture).delivery_mode as string;
      const recordedAuthority = fixture(`GET ${path}`) as Json;
      return json({ ...recordedAuthority, configured_mode: mode, effective_mode: mode, state: mode === 'manual' ? 'manual' : 'active' });
    }
    if (path === `/projects/${PROJECT}/assessments`) {
      const recordedList = (fixture(`GET ${path}`) as { items: Json[] }).items.filter(a => !HIDDEN_IDS.has(a.id as string) && (!repoParam || a.repo_id === repoParam));
      return json(page(byNewest([...recordedList, ...runAssessments(state, now, repoParam)])));
    }
    if (path === `/projects/${PROJECT}/findings`) {
      const recordedList = (fixture(`GET ${path}`) as { items: Json[] }).items.filter(f => !HIDDEN_IDS.has(f.id as string) && !HIDDEN_IDS.has(f.assessment_id as string));
      const replayed = state.runs.filter(run => !repoParam || run.repoId === repoParam).flatMap(run => slice(run, now).findings);
      const repoFiltered = repoParam && repoParam !== REPO ? [] : recordedList;
      return json(page(byNewest([...replayed, ...repoFiltered])));
    }
    if (path === `/projects/${PROJECT}/approvals`) {
      const recordedList = (fixture(`GET /projects/${PROJECT}/approvals`) as { items: Json[] }).items.filter(a => !HIDDEN_IDS.has(a.id as string));
      const replayed = state.runs.filter(run => !repoParam || run.repoId === repoParam).flatMap(run => runApprovals(run, state, now));
      let items = [...replayed, ...state.approvals, ...(repoParam && repoParam !== REPO ? [] : recordedList)];
      const status = query.get('status');
      if (status) items = items.filter(a => a.status === status);
      return json(page(items.sort((a, b) => String(b.requested_at).localeCompare(String(a.requested_at)))));
    }
    if (parts[0] === 'assessments' && parts[1]) {
      if (parts[1] === HIDDEN) return error(404, 'NOT_FOUND', 'Not part of the demo account');
      const run = runOf(parts[1], state);
      if (!run) return undefined;
      const current = slice(run, now);
      if (parts.length === 2) return json({ assessment: current.assessment, agent_runs: current.agent_runs, findings: current.findings });
      if (parts[2] === 'runs') return json(page(current.agent_runs));
      const after = Number(query.get('after') ?? 0) || 0;
      if (parts[2] === 'events' && parts[3] === 'log') return json(page(current.events.filter(e => (e.seq as number) > after)));
      if (parts[2] === 'events') return sse(run, after, signal);
      if (parts[2] === 'report') {
        if (!current.line.done) return error(409, 'CONFLICT_STATE', 'The report is written when the assessment finishes.');
        return json(retime(run, current.line, rekey(run, raw(`GET /assessments/${TEMPLATE}/report`))));
      }
      return undefined;
    }
    if (parts[0] === 'findings' && parts[1]) {
      if (HIDDEN_IDS.has(parts[1])) return error(404, 'NOT_FOUND', 'Not part of the demo account');
      const run = runForRecord(parts[1], state);
      if (!run) return undefined;
      const current = slice(run, now);
      const replayed = current.findings.find(f => f.id === parts[1]);
      if (!replayed) return error(404, 'NOT_FOUND', 'This finding has not been recorded yet.');
      const base = baseId(parts[1]);
      if (parts.length === 2) {
        const detail = retime(run, current.line, rekey(run, raw(`GET /findings/${base}`))) as Json;
        return json({ ...detail, finding: { ...(detail.finding as Json), status: replayed.status, history: replayed.history } });
      }
      if (parts[2] === 'patches') {
        const patched = current.events.some(e => e.type === 'agent_run.finished' && e.agent === 'patch');
        return json(patched ? retime(run, current.line, rekey(run, raw(`GET /findings/${base}/patches`))) : page([]));
      }
      return undefined;
    }
    return undefined;
  }

  // ---- writes: recorded in this tab only

  if (method === 'PATCH' && path === `/projects/${PROJECT}`) {
    if (input.settings && typeof input.settings === 'object') state.settings = input.settings as Json;
    save(state);
    return json(project(state, fixture));
  }
  if (method === 'POST' && path === `/projects/${PROJECT}/repositories`) {
    const fullName = String(input.full_name ?? '');
    const source = demoRepoFor(fullName);
    if (!source) return error(403, 'FORBIDDEN', 'The demo GitHub App installation cannot reach that repository.');
    const existing = repositories(state, fixture).find(r => r.full_name === fullName);
    if (existing) return json(existing);
    const repo = { automatic_assessments: false, id: `rep_demo_${source.name}`, project_id: PROJECT, provider: 'github', full_name: fullName, default_branch: source.defaultBranch, installation_id: INSTALLATION, disconnected_at: null, disconnected: false, created_at: iso(now) };
    state.repos.push(repo);
    save(state);
    return json(repo, 201);
  }
  if (parts[0] === 'repositories' && parts[1] && method === 'PATCH') {
    const repoId = parts[1];
    if (!repositories(state, fixture).some(r => r.id === repoId)) return undefined;
    if (parts.length === 2) {
      state.auto[repoId] = input.automatic_assessments === true;
      save(state);
      return json(repositories(state, fixture).find(r => r.id === repoId));
    }
    if (parts[2] === 'setup') {
      const complete = input.complete === true;
      const previous = state.setups[repoId];
      state.setups[repoId] = { repo_id: repoId, answers: input.answers, complete, completed_at: complete ? (previous?.completed_at ?? iso(now)) : null, updated_at: iso(now) };
      save(state);
      return json(state.setups[repoId]);
    }
  }
  if (method === 'POST' && path === `/projects/${PROJECT}/scopes`) {
    state.counter += 1;
    const scope = {
      id: `scp_demo_${String(state.counter).padStart(4, '0')}`,
      name: String(input.name ?? 'Sandbox testing'),
      notes: input.notes ?? null,
      status: 'pending',
      targets: input.targets ?? [],
      expires_at: input.expires_at,
      project_id: PROJECT,
      approved_at: null,
      approved_by: null,
      requested_by: USER,
      allowed_check_categories: input.allowed_check_categories ?? [],
    };
    state.scopes.push(scope);
    save(state);
    return json(scope, 201);
  }
  if (method === 'POST' && parts[0] === 'scopes' && parts[1] && (parts[2] === 'approve' || parts[2] === 'revoke')) {
    const scope = state.scopes.find(s => s.id === parts[1]);
    if (!scope) return error(403, 'FORBIDDEN', 'Recorded sample scopes cannot be changed in the demo account.');
    if (parts[2] === 'approve') {
      Object.assign(scope, { status: 'active', approved_at: iso(now), approved_by: USER });
      state.approvals.push({ id: `apv_demo_${scope.id as string}`, reason: null, status: 'approved', decided_at: iso(now), decided_by: USER, project_id: PROJECT, subject_id: scope.id, requested_at: iso(now), requested_by: USER, subject_type: 'scope' });
    } else {
      scope.status = 'revoked';
    }
    save(state);
    return json(scope);
  }
  if (method === 'POST' && path === `/projects/${PROJECT}/assessments`) {
    const repoId = String(input.repo_id ?? '');
    const repo = repositories(state, fixture).find(r => r.id === repoId);
    if (!repo) return error(404, 'NOT_FOUND', 'Repository not found');
    const scope = activeScopeFor(repoId, state, fixture, now);
    if (!scope || (input.scope_id && input.scope_id !== scope.id)) return error(403, 'SCOPE_DENIED', 'No approved sandbox scope covers this repository.');
    const requested = typeof input.commit_sha === 'string' && input.commit_sha ? input.commit_sha : null;
    const commits = (commitsFor(repoId, state, now, fixture)?.items as Json[] | undefined) ?? [];
    const full = repoId === REPO && (requested ?? recordedSha) === recordedSha;
    // Other repositories replay a clean run, so it starts on a commit the sample data calls quiet.
    const quiet = demoRepoFor(repo.full_name as string)?.commits.find(c => c.scenario === 'clean' || c.scenario === 'dependency')?.sha;
    const sha = requested ?? (full ? recordedSha : quiet ?? (commits[0]?.sha as string | undefined) ?? recordedSha);
    state.counter += 1;
    const run: Run = { id: `${TEMPLATE}-${full ? 'r' : 'c'}${state.counter}`, kind: full ? 'full' : 'clean', repoId, sha, scopeId: scope.id as string, startedAt: now, decidedAt: null, declined: false };
    state.runs.push(run);
    save(state);
    return json({ assessment: slice(run, now).assessment }, 202);
  }
  if (method === 'POST' && parts[0] === 'approvals' && parts[1] && parts[2] === 'decision') {
    const run = runForRecord(parts[1], state);
    if (!run) return error(403, 'FORBIDDEN', 'Recorded sample decisions cannot be changed in the demo account.');
    const approval = runApprovals(run, state, now).find(a => a.id === parts[1]);
    if (!approval) return error(404, 'NOT_FOUND', 'Approval not found');
    if (approval.status !== 'pending') return error(409, 'CONFLICT_STATE', 'This approval was already decided.');
    const status = input.decision === 'declined' ? 'declined' : 'approved';
    state.decisions[parts[1]] = { status, reason: typeof input.reason === 'string' ? input.reason : null, at: now };
    const all = runApprovals(run, state, now);
    if (all.every(a => a.status !== 'pending') && slice(run, now).line.paused) {
      run.decidedAt = now;
      run.declined = all.some(a => a.status === 'declined');
    }
    save(state);
    return json(runApprovals(run, state, now).find(a => a.id === parts[1]));
  }
  if (method === 'POST' && parts[0] === 'assessments' && parts[1] && parts[2] === 'cancel') {
    return error(403, 'FORBIDDEN', 'This is the demo account: recorded checks cannot be cancelled.');
  }
  return undefined;
}
