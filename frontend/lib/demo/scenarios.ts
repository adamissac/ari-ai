/**
 * Simulated analysis of one demo commit (ADR 0013). Illustrative only: the review, the seven
 * agent runs, the patch and the defense state are hand-written stories shaped like the real
 * contracts (AgentRun tool calls, findings, verification), not records of an execution.
 */
import type { DemoCommit, DemoComponent, DemoRepo, ScenarioId } from '@/lib/demo/data';

export type Lang = 'py' | 'ts' | 'rs';
export type LineKind = '+' | '-' | ' ';
export interface DiffLine { kind: LineKind; text: string }
export interface DiffFile { path: string; additions: number; deletions: number; hunks: { header: string; lines: DiffLine[] }[] }

export interface ReviewComment { path: string; line: string; severity: 'blocker' | 'major' | 'note'; title: string; body: string }
export interface Expectation { id: string; text: string; source: string }
export interface GeneratedTest { name: string; expectation: string; before: 'fail' | 'pass'; after: 'pass' }

export type AgentId = 'scout' | 'probe' | 'trace' | 'diagnose' | 'patch' | 'fortify' | 'verify';
/** `on` names the kind of app part a step is about (e.g. 'logging'); unset, the map infers it. */
export interface ToolStep { tool: string; input: string; result: string; ms: number; outcome: 'ok' | 'denied'; on?: string }
export interface AgentRunView {
  agent: AgentId;
  label: string;
  team: 'Red' | 'Blue' | 'Independent';
  job: string;
  status: 'done' | 'skipped';
  outcome: string;
  evidence: string[];
  steps: ToolStep[];
  handoff: string;
  seconds: number;
  tokens: number;
}

export type WatchState = 'healthy' | 'checking' | 'attention' | 'hardened';
export interface DefenseView {
  watch: Record<string, WatchState>;
  checkedMinutesAgo: Record<string, number>;
  recommendation: { action: string; target: string; why: string; confidence: number };
  events: { minutesAgo: number; text: string; tone: 'ok' | 'warn' | 'info' }[];
}

/** `on` is the kind of app part the finding is in; unset, it is the changed service. */
export interface Finding { id: string; title: string; kind: 'security' | 'functional'; cwe: string; severity: 'critical' | 'high' | 'medium' | 'low'; cvss: string; where: string; on?: string }
/** A suspicion the red team raised and Probe refuted: shown as a false alarm on that part. */
export interface FalseAlarm { on: string; text: string }

export interface Analysis {
  headline: string;
  summary: string;
  seconds: number;
  usd: number;
  findings: Finding[];
  falseAlarms?: FalseAlarm[];
  review: {
    intent: string;
    expectations: Expectation[];
    diff: DiffFile[];
    comments: ReviewComment[];
    tests: GeneratedTest[];
    verdict: string;
  };
  agents: AgentRunView[];
  patch: DiffFile | null;
  defense: DefenseView;
}

export const AGENT_ORDER: { agent: AgentId; label: string; team: AgentRunView['team']; job: string }[] = [
  { agent: 'scout', label: 'Scout', team: 'Red', job: 'Map the attack surface' },
  { agent: 'probe', label: 'Probe', team: 'Red', job: 'Prove or disprove' },
  { agent: 'trace', label: 'Trace', team: 'Red', job: 'Follow the path' },
  { agent: 'diagnose', label: 'Diagnose', team: 'Blue', job: 'Find the cause' },
  { agent: 'patch', label: 'Patch', team: 'Blue', job: 'Propose a fix' },
  { agent: 'fortify', label: 'Fortify', team: 'Blue', job: 'Prevent recurrence' },
  { agent: 'verify', label: 'Verify', team: 'Independent', job: 'Accept on evidence' },
];

export function langOf(repo: DemoRepo): Lang {
  if (repo.language === 'TypeScript') return 'ts';
  if (repo.language === 'Rust') return 'rs';
  return 'py';
}

function run(agent: AgentId, rest: Omit<AgentRunView, 'agent' | 'label' | 'team' | 'job'>): AgentRunView {
  const role = AGENT_ORDER.find(item => item.agent === agent)!;
  return { agent, label: role.label, team: role.team, job: role.job, ...rest };
}

function skipped(agent: AgentId, why: string): AgentRunView {
  return run(agent, { status: 'skipped', outcome: why, evidence: [], steps: [], handoff: 'Nothing to hand off.', seconds: 0, tokens: 0 });
}

const L = (kind: LineKind, text: string): DiffLine => ({ kind, text });
const count = (lines: DiffLine[], kind: LineKind) => lines.filter(l => l.kind === kind).length;
function file(path: string, header: string, lines: DiffLine[]): DiffFile {
  return { path, additions: count(lines, '+'), deletions: count(lines, '-'), hunks: [{ header, lines }] };
}

function watchAll(components: DemoComponent[], state: WatchState, overrides: Record<string, WatchState> = {}): Record<string, WatchState> {
  return Object.fromEntries(components.map(c => [c.id, overrides[c.id] ?? state]));
}
function checkedAgo(components: DemoComponent[], seed: number): Record<string, number> {
  return Object.fromEntries(components.map((c, i) => [c.id, 1 + ((seed + i * 7) % 11)]));
}
function serviceId(repo: DemoRepo): string {
  return repo.components.find(c => c.kind === 'service')?.id ?? repo.components[0]!.id;
}

// ---------------------------------------------------------------- authz (CWE-639)

function authz(repo: DemoRepo, commit: DemoCommit): Analysis {
  const ts = langOf(repo) === 'ts';
  const noun = repo.name === 'fleet-portal' ? 'device' : repo.name === 'checkout-web' ? 'order' : 'payment';
  const route = `GET /${noun}s/{${noun}_id}`;
  const path = ts ? `src/routes/${noun}s.ts` : 'payments_api/app.py';
  const diff = ts
    ? file(path, `@@ -41,6 +41,18 @@ export const ${noun}Routes = router();`, [
      L(' ', `${noun}Routes.get('/${noun}s', requireSession, async (req, res) => {`),
      L(' ', `  res.json(await db.${noun}s.listForOwner(req.user.id));`),
      L(' ', '});'),
      L('+', ''),
      L('+', `/** Return one ${noun} by id. */`),
      L('+', `${noun}Routes.get('/${noun}s/:id', requireSession, async (req, res) => {`),
      L('+', `  const ${noun} = await db.${noun}s.findById(req.params.id);`),
      L('+', `  if (!${noun}) return res.status(404).json({ error: 'not found' });`),
      L('+', `  res.json(serialize(${noun}));`),
      L('+', '});'),
    ])
    : file(path, '@@ -128,6 +128,17 @@ def create_app(store: Store | None = None) -> FastAPI:', [
      L(' ', '        return payment_out(store, p)'),
      L(' ', ''),
      L('+', '    @app.get("/payments/{payment_id}", response_model=PaymentOut)'),
      L('+', '    def get_payment('),
      L('+', '        payment_id: str,'),
      L('+', '        customer: Customer = Depends(current_customer),'),
      L('+', '        store: Store = Depends(get_store),'),
      L('+', '    ) -> PaymentOut:'),
      L('+', '        """Return one payment by id."""'),
      L('+', '        p = store.payments.get(payment_id)'),
      L('+', '        if p is None:'),
      L('+', '            raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")'),
      L('+', '        return payment_out(store, p)'),
    ]);
  const patch = ts
    ? file(path, `@@ -46,4 +46,6 @@ ${noun}Routes.get('/${noun}s/:id', requireSession, async (req, res) => {`, [
      L(' ', `  const ${noun} = await db.${noun}s.findById(req.params.id);`),
      L(' ', `  if (!${noun}) return res.status(404).json({ error: 'not found' });`),
      L('+', `  if (${noun}.ownerId !== req.user.id) return res.status(404).json({ error: 'not found' });`),
      L('+', `  await audit.record('${noun}.read', ${noun}.id, req.user.id);`),
      L(' ', `  res.json(serialize(${noun}));`),
    ])
    : file(path, '@@ -136,5 +136,7 @@ def get_payment(', [
      L(' ', '        p = store.payments.get(payment_id)'),
      L(' ', '        if p is None:'),
      L(' ', '            raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")'),
      L('+', '        require_owner(p.customer_id, customer)'),
      L('+', '        audit.record("payment.read", p.id, customer.id)'),
      L(' ', '        return payment_out(store, p)'),
    ]);
  const guard = ts ? 'ownerId check' : 'require_owner()';
  const svc = serviceId(repo);
  return {
    headline: `Two confirmed issues: another customer's ${noun} could be read, with no trace in the audit log`,
    summary: `The new ${route} handler skipped the ownership check and the audit record its sibling routes use. Probe confirmed both in the sandbox with two test identities and refuted a third suspicion (an edge rate-limit bypass: a false alarm). Patch added the check and the audit call, and Verify accepted the fix after the exploit test failed against the patched build.`,
    seconds: 412, usd: 1.84,
    findings: [
      { id: `fnd_${commit.sha.slice(0, 6)}_authz`, title: `Missing ownership check on ${route}`, kind: 'security', cwe: 'CWE-639 Authorization bypass through user-controlled key', severity: 'high', cvss: '7.1', where: `${path} · ${route}`, on: 'service' },
      { id: `fnd_${commit.sha.slice(0, 6)}_audit`, title: `Reads through ${route} leave no audit record`, kind: 'security', cwe: 'CWE-778 Insufficient logging', severity: 'medium', cvss: '4.3', where: `${path} · ${route}`, on: 'logging' },
    ],
    falseAlarms: [{ on: 'edge', text: 'The new route might bypass the edge rate limit' }],
    review: {
      intent: `Add a lookup for a single ${noun} so support tooling and the app can fetch it by id.`,
      expectations: [
        { id: 'exp_owner_only', text: `A customer can only read ${noun}s they own.`, source: ts ? `README.md §Access, convention in ${noun}s.listForOwner` : 'module docstring, require_owner() convention on sibling routes' },
        { id: 'exp_404_not_403', text: 'Unknown or foreign ids return 404, never 403, so existence does not leak.', source: ts ? 'docs/api.md' : 'require_owner() docstring' },
      ],
      diff: [diff],
      comments: [
        { path, line: ts ? 'L49' : 'L137', severity: 'blocker', title: 'Ownership check missing', body: `Every sibling route calls ${guard} before returning a resource. This handler returns any ${noun} whose id is known. Handed to the security team to prove it in the sandbox.` },
        { path, line: ts ? 'L45' : 'L135', severity: 'note', title: 'Docstring does not state the access rule', body: `Say who may read a ${noun} so the rule stays attached to the code.` },
      ],
      tests: [
        { name: `test_${noun}_lookup_returns_own_${noun}`, expectation: 'exp_owner_only', before: 'pass', after: 'pass' },
        { name: `test_${noun}_lookup_hides_foreign_${noun}`, expectation: 'exp_owner_only', before: 'fail', after: 'pass' },
        { name: `test_unknown_${noun}_is_404`, expectation: 'exp_404_not_403', before: 'pass', after: 'pass' },
      ],
      verdict: 'Behaviour matches the intent for the owner, but the change breaks the ownership expectation. Sent to security instead of being repaired as a functional bug.',
    },
    agents: [
      run('scout', {
        status: 'done', seconds: 48, tokens: 18_420,
        outcome: `Raised 3 hypotheses on the change: ${route} skips the ownership check (H1), its reads are not audited (H2), and it may bypass the edge rate limit (H3).`,
        evidence: [`${route}: no ${guard} on the read path (sibling routes all have it)`, 'No audit record on the new read (4 of 4 sibling reads write one)', 'Edge rate-limit rules match routes by prefix; the new route might not be covered'],
        steps: [
          { tool: 'intel.changed_symbols', input: `commit ${commit.sha.slice(0, 7)}`, result: `1 new route, 0 removed`, ms: 220, outcome: 'ok', on: 'service' },
          { tool: 'intel.call_graph', input: route, result: `handler → db lookup → serialize (no ${guard})`, ms: 410, outcome: 'ok', on: 'service' },
          { tool: 'intel.convention', input: 'ownership checks on sibling routes', result: `${guard} on 4 of 4 sibling reads`, ms: 290, outcome: 'ok', on: 'service' },
          { tool: 'intel.convention', input: 'audit records on sibling reads', result: 'audit.record on 4 of 4 sibling reads, none on the new route', ms: 260, outcome: 'ok', on: 'logging' },
          { tool: 'intel.entry_points', input: 'edge rate-limit rules', result: 'the new route is not listed by name', ms: 180, outcome: 'ok', on: 'edge' },
          { tool: 'record.hypothesis', input: 'H1 ownership, H2 audit gap, H3 rate-limit bypass', result: '3 hypotheses saved', ms: 35, outcome: 'ok', on: 'service' },
        ],
        handoff: 'Three hypotheses for Probe, ranked. None is confirmed yet.',
      }),
      run('probe', {
        status: 'done', seconds: 96, tokens: 22_310,
        outcome: `Confirmed H1: customer B read customer A's ${noun} (HTTP 200). Confirmed H2: that read left no audit record. Refuted H3: the edge rate-limits the new route like every other (a false alarm).`,
        evidence: [`GET /${noun}s/${noun.slice(0, 3)}_1001 as cus_b → 200 with cus_a's record`, 'Audit log after the read: no entry (H2 confirmed)', '60 lookups in 10 s through the edge → 429 after 30 (H3 refuted)', 'Every request stayed inside the approved sandbox scope'],
        steps: [
          { tool: 'sandbox.start', input: `${repo.name}@${commit.sha.slice(0, 7)} (no network egress)`, result: 'container healthy in 8.4 s', ms: 8_420, outcome: 'ok', on: 'service' },
          { tool: 'fixture.identities', input: 'cus_a, cus_b', result: '2 bearer tokens issued inside the sandbox', ms: 120, outcome: 'ok', on: 'service' },
          { tool: 'http.request', input: `GET /${noun}s/${noun.slice(0, 3)}_1001 as cus_a`, result: '200 (own record)', ms: 31, outcome: 'ok', on: 'service' },
          { tool: 'http.request', input: `GET /${noun}s/${noun.slice(0, 3)}_1001 as cus_b`, result: "200 — returned cus_a's record", ms: 29, outcome: 'ok', on: 'service' },
          { tool: 'http.request', input: 'GET https://api.stripe.com/v1/charges', result: 'denied: host is outside the authorized scope', ms: 2, outcome: 'denied', on: 'service' },
          { tool: 'http.request', input: 'read the audit log after the lookup', result: 'no entry for the read (H2 confirmed)', ms: 24, outcome: 'ok', on: 'logging' },
          { tool: 'http.request', input: '60 lookups in 10 s through the edge', result: '429 after 30: the rate limit applies (H3 refuted)', ms: 410, outcome: 'ok', on: 'edge' },
          { tool: 'record.check', input: 'ownership, audit, rate limit', result: 'H1 confirmed · H2 confirmed · H3 refuted', ms: 40, outcome: 'ok', on: 'service' },
        ],
        handoff: 'Two confirmed weaknesses with the exact requests and responses. One hypothesis refuted: a false alarm.',
      }),
      run('trace', {
        status: 'done', seconds: 41, tokens: 9_870,
        outcome: `Reachable from the internet through the edge with any valid session. Exposes amount, currency and description of every ${noun}.`,
        evidence: [`edge → ${repo.components.find(c => c.id === svc)?.label} → data store: 3 hops, 1 auth check (session only)`, 'Ids are sequential, so enumeration is cheap', 'Write paths are not affected (unverified hypothesis, labelled)'],
        steps: [
          { tool: 'intel.path', input: `internet → ${route}`, result: '3 hops, session required, no ownership gate', ms: 260, outcome: 'ok' },
          { tool: 'intel.data_classes', input: `${noun} serializer`, result: 'amount, currency, description, customer id', ms: 180, outcome: 'ok' },
          { tool: 'intel.path', input: 'audit pipeline', result: 'the read bypasses audit.record, so the leak is invisible to monitoring', ms: 190, outcome: 'ok', on: 'logging' },
          { tool: 'record.attack_path', input: 'P1', result: 'saved with 1 unverified step', ms: 30, outcome: 'ok' },
        ],
        handoff: 'Attack path with impact. One step stays a hypothesis.',
      }),
      run('diagnose', {
        status: 'done', seconds: 37, tokens: 8_940,
        outcome: `Root cause: the new handler was written without the ${guard} step and the audit record every sibling route has. Fix both in one place; no schema change.`,
        evidence: [`Convention: ${guard} on 4 of 4 sibling routes`, 'CVSS 3.1 AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:N/A:N → 7.1 High', `Remediation: call ${guard} after the not-found check, keep 404`],
        steps: [
          { tool: 'intel.symbol', input: guard, result: 'defined once, used by 4 routes', ms: 150, outcome: 'ok' },
          { tool: 'score.cvss31', input: 'confirmed check + attack path', result: '7.1 High', ms: 20, outcome: 'ok' },
          { tool: 'intel.symbol', input: 'audit.record', result: 'used by 4 sibling reads', ms: 120, outcome: 'ok', on: 'logging' },
          { tool: 'score.cvss31', input: 'H2 audit gap', result: '4.3 Medium', ms: 20, outcome: 'ok', on: 'logging' },
          { tool: 'record.remediation_plan', input: 'RP1', result: 'awaiting human approval', ms: 25, outcome: 'ok' },
        ],
        handoff: `Remediation plan. Approved by ${commit.author} at 2:14 PM; only then did Patch start.`,
      }),
      run('patch', {
        status: 'done', seconds: 64, tokens: 14_200,
        outcome: `Added ${guard} and the audit record to ${route} in an isolated worktree. 2 lines, nothing merged.`,
        evidence: [`Diff: +2 −0 in ${path}`, "Existing test suite: 31 passed", 'Worktree discarded after export; production untouched'],
        steps: [
          { tool: 'worktree.create', input: `${commit.sha.slice(0, 7)} (isolated)`, result: 'ready', ms: 900, outcome: 'ok' },
          { tool: 'fs.edit', input: `${path} (ownership check)`, result: '+1 −0', ms: 40, outcome: 'ok' },
          { tool: 'fs.edit', input: `${path} (audit record)`, result: '+1 −0', ms: 35, outcome: 'ok', on: 'logging' },
          { tool: 'sandbox.run_tests', input: ts ? 'npm test' : 'pytest -q', result: '31 passed', ms: 7_800, outcome: 'ok' },
          { tool: 'git.push', input: 'origin main', result: 'denied: Patch may not push or merge', ms: 1, outcome: 'denied' },
          { tool: 'record.patch_candidate', input: 'PC1', result: 'saved for independent verification', ms: 30, outcome: 'ok' },
        ],
        handoff: 'A candidate diff for Verify. Not merged.',
      }),
      run('fortify', {
        status: 'done', seconds: 33, tokens: 7_410,
        outcome: 'Added a regression test and a lint rule that flags any new read route without an ownership check.',
        evidence: [`Regression test test_${noun}_lookup_hides_foreign_${noun}`, `Rule: routes under /${noun}s/{id} must call ${guard}`, 'Defense recommendation: raise monitoring on the API node for 24 h'],
        steps: [
          { tool: 'tests.generate', input: 'exp_owner_only', result: '1 regression test', ms: 2_100, outcome: 'ok' },
          { tool: 'policy.suggest_rule', input: 'ownership convention', result: '1 rule proposed', ms: 300, outcome: 'ok' },
          { tool: 'rl.recommend', input: 'confirmed finding on API node', result: 'monitor:api (simulation-derived)', ms: 60, outcome: 'ok' },
        ],
        handoff: 'Hardening notes and a regression test for Verify to run.',
      }),
      run('verify', {
        status: 'done', seconds: 93, tokens: 11_630,
        outcome: 'Accepted. The exploit request now gets 404, the read is written to the audit log, and all functional tests pass on the patched build.',
        evidence: ['Exploit replay as cus_b: 200 before → 404 after', 'Functional: 34 passed (31 existing + 3 generated)', 'Verified against the exact bytes of the candidate diff (sha256 bound)'],
        steps: [
          { tool: 'sandbox.start', input: 'patched build (fresh container)', result: 'healthy in 8.1 s', ms: 8_100, outcome: 'ok' },
          { tool: 'http.request', input: `GET /${noun}s/${noun.slice(0, 3)}_1001 as cus_b`, result: '404 not found', ms: 28, outcome: 'ok' },
          { tool: 'http.request', input: 'read as cus_a, then the audit log', result: '1 audit entry recorded', ms: 26, outcome: 'ok', on: 'logging' },
          { tool: 'sandbox.run_tests', input: 'existing + generated', result: '34 passed', ms: 9_400, outcome: 'ok' },
          { tool: 'record.verification', input: 'PC1', result: 'accepted', ms: 30, outcome: 'ok' },
        ],
        handoff: 'Pass. The finding is now verified as fixed in the candidate diff, ready for a pull request.',
      }),
    ],
    patch,
    defense: {
      watch: watchAll(repo.components, 'healthy', { [svc]: 'hardened' }),
      checkedMinutesAgo: checkedAgo(repo.components, commit.minutesAgo),
      recommendation: { action: 'Raise monitoring', target: repo.components.find(c => c.id === svc)!.label, why: 'A confirmed access-control weakness was fixed here today. Watch for enumeration attempts against the old behaviour.', confidence: 0.82 },
      events: [
        { minutesAgo: 2, text: `Verify accepted the fix for ${route}`, tone: 'ok' },
        { minutesAgo: 6, text: `Probe confirmed the ownership bypass in the sandbox`, tone: 'warn' },
        { minutesAgo: commit.minutesAgo, text: `Push to ${commit.branch} started a check`, tone: 'info' },
      ],
    },
  };
}

// ---------------------------------------------------------------- refund bound (CWE-840)

function refund(repo: DemoRepo, commit: DemoCommit): Analysis {
  const path = repo.name === 'ledger-service' ? 'ledger/settlement.py' : 'payments_api/app.py';
  const diff = file(path, '@@ -151,9 +151,11 @@ def create_refund(', [
    L(' ', '        p = store.payments.get(body.payment_id)'),
    L(' ', '        if p is None:'),
    L(' ', '            raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")'),
    L(' ', '        require_owner(p.customer_id, customer)'),
    L('-', '        if store.refunds_for(p.id):'),
    L('-', '            raise HTTPException(status.HTTP_409_CONFLICT, "already refunded")'),
    L('+', '        # Partial refunds: several refunds may be issued for one payment.'),
    L('+', '        if body.amount > p.amount:'),
    L('+', '            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "refund exceeds payment")'),
    L(' ', '        r = Refund(store.next_id("ref"), p.id, body.amount, body.reason)'),
  ]);
  const patch = file(path, '@@ -155,3 +155,4 @@ def create_refund(', [
    L('+', '        already = sum((r.amount for r in store.refunds_for(p.id)), Decimal("0"))'),
    L('-', '        if body.amount > p.amount:'),
    L('+', '        if already + body.amount > p.amount:'),
    L(' ', '            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "refund exceeds payment")'),
  ]);
  const db = repo.components.find(c => c.kind === 'data')?.id ?? serviceId(repo);
  return {
    headline: 'Several partial refunds could add up to more than the payment',
    summary: 'The change allowed partial refunds but compared only the new refund with the payment amount. The reviewer generated a test that failed on the change, repaired the check, and the repair passed every test. Security agents confirmed there was no further exposure.',
    seconds: 268, usd: 0.97,
    findings: [{ id: `fnd_${commit.sha.slice(0, 6)}_refund`, title: 'Total refunds can exceed the original payment', kind: 'functional', cwe: 'CWE-840 Business logic errors', severity: 'high', cvss: '—', where: `${path} · POST /refunds` }],
    review: {
      intent: 'Allow refunding part of a payment, in more than one step.',
      expectations: [
        { id: 'exp_refund_bound', text: "Total refunds for a payment must never exceed the payment's original amount.", source: 'module docstring, README §Refunds' },
        { id: 'exp_positive_amounts', text: 'Amounts are positive with two decimal places.', source: 'RefundIn model' },
      ],
      diff: [diff],
      comments: [
        { path, line: 'L156', severity: 'blocker', title: 'Bound ignores earlier refunds', body: 'Two refunds of 60.00 on a 100.00 payment both pass this check. Compare the running total, not just the new amount. The generated test below fails on this commit.' },
      ],
      tests: [
        { name: 'test_single_partial_refund_allowed', expectation: 'exp_refund_bound', before: 'pass', after: 'pass' },
        { name: 'test_refunds_cannot_exceed_payment_in_total', expectation: 'exp_refund_bound', before: 'fail', after: 'pass' },
        { name: 'test_refund_amount_must_be_positive', expectation: 'exp_positive_amounts', before: 'pass', after: 'pass' },
      ],
      verdict: 'Functional bug. Repaired by the reviewer; the repair passes the generated and the existing tests.',
    },
    agents: [
      run('scout', {
        status: 'done', seconds: 39, tokens: 15_220,
        outcome: 'One hypothesis: repeated partial refunds could drain more money than was paid (business logic).',
        evidence: ['POST /refunds: bound uses body.amount only', 'Ownership check present (require_owner) → access control not in question'],
        steps: [
          { tool: 'intel.changed_symbols', input: `commit ${commit.sha.slice(0, 7)}`, result: '1 handler changed', ms: 200, outcome: 'ok' },
          { tool: 'review.findings', input: 'functional handoff', result: 'fnd refund bound (repaired by reviewer)', ms: 60, outcome: 'ok' },
          { tool: 'record.hypothesis', input: 'H1 refund drain', result: 'saved', ms: 30, outcome: 'ok' },
        ],
        handoff: 'One hypothesis for Probe.',
      }),
      run('probe', {
        status: 'done', seconds: 71, tokens: 17_900,
        outcome: 'Confirmed on the original commit: two 60.00 refunds succeeded on a 100.00 payment. Refuted on the reviewer\'s repaired build.',
        evidence: ['Original: refunds of 60.00 + 60.00 → 201, 201 (total 120.00)', 'Repaired: second refund → 422 refund exceeds payment'],
        steps: [
          { tool: 'sandbox.start', input: `${repo.name}@${commit.sha.slice(0, 7)}`, result: 'healthy in 7.9 s', ms: 7_900, outcome: 'ok' },
          { tool: 'http.request', input: 'POST /refunds 60.00 (pay_1001, 100.00)', result: '201', ms: 33, outcome: 'ok' },
          { tool: 'http.request', input: 'POST /refunds 60.00 (pay_1001)', result: '201 — total refunded 120.00', ms: 30, outcome: 'ok' },
          { tool: 'record.check', input: 'business_logic.refund_bound', result: 'confirmed on original', ms: 30, outcome: 'ok' },
        ],
        handoff: 'Confirmed on the original commit; already repaired by the reviewer.',
      }),
      run('trace', {
        status: 'done', seconds: 22, tokens: 5_100,
        outcome: 'Impact limited to the refund worker and ledger. Any signed-in customer could refund their own payment above its value.',
        evidence: ['edge → api → refund worker → ledger', 'Requires ownership of the payment, so no cross-customer impact'],
        steps: [{ tool: 'intel.path', input: 'POST /refunds', result: '4 hops, owner-only', ms: 230, outcome: 'ok' }],
        handoff: 'Impact scoped to own payments.',
      }),
      run('diagnose', {
        status: 'done', seconds: 18, tokens: 4_300,
        outcome: 'Root cause: removing the "already refunded" check without replacing it with a running-total check.',
        evidence: ['The old guard (409 already refunded) was the only bound on repeated refunds'],
        steps: [{ tool: 'git.blame', input: `${path}:155`, result: `removed in ${commit.sha.slice(0, 7)}`, ms: 120, outcome: 'ok' }],
        handoff: "Points to the reviewer's repair; no separate patch needed.",
      }),
      skipped('patch', "Not needed: the reviewer's repair already covers this finding. Patch only runs on security findings with an approved plan."),
      run('fortify', {
        status: 'done', seconds: 21, tokens: 4_800,
        outcome: 'Suggested a database constraint so the ledger itself refuses refunds above the payment total.',
        evidence: ['CHECK (refunded_total <= amount) on payments', 'Regression test test_refunds_cannot_exceed_payment_in_total'],
        steps: [{ tool: 'policy.suggest_rule', input: 'exp_refund_bound', result: '1 constraint proposed', ms: 280, outcome: 'ok' }],
        handoff: 'Hardening note for the team; optional.',
      }),
      run('verify', {
        status: 'done', seconds: 61, tokens: 9_200,
        outcome: 'Accepted the reviewer\'s repair: the exploit sequence now stops at 422 and all 33 tests pass.',
        evidence: ['Exploit replay: 201, 422 (total stays 60.00)', 'Functional: 33 passed (30 existing + 3 generated)'],
        steps: [
          { tool: 'sandbox.start', input: 'repaired build', result: 'healthy in 7.7 s', ms: 7_700, outcome: 'ok' },
          { tool: 'sandbox.run_tests', input: 'existing + generated', result: '33 passed', ms: 8_200, outcome: 'ok' },
          { tool: 'record.verification', input: 'reviewer repair', result: 'accepted', ms: 30, outcome: 'ok' },
        ],
        handoff: 'Pass.',
      }),
    ],
    patch,
    defense: {
      watch: watchAll(repo.components, 'healthy', { [db]: 'hardened' }),
      checkedMinutesAgo: checkedAgo(repo.components, commit.minutesAgo),
      recommendation: { action: 'Request re-check', target: repo.components.find(c => c.id === db)!.label, why: 'Refund totals were unbounded for a short window. Re-check that no payment was over-refunded.', confidence: 0.74 },
      events: [
        { minutesAgo: 4, text: 'Verify accepted the reviewer repair for POST /refunds', tone: 'ok' },
        { minutesAgo: 9, text: 'Generated test failed on the original commit (expected)', tone: 'warn' },
        { minutesAgo: commit.minutesAgo, text: `Push to ${commit.branch} started a check`, tone: 'info' },
      ],
    },
  };
}

// ---------------------------------------------------------------- injection (CWE-89)

function injection(repo: DemoRepo, commit: DemoCommit): Analysis {
  const ts = langOf(repo) === 'ts';
  const path = ts ? 'src/routes/search.ts' : 'payments_api/search.py';
  const diff = ts
    ? file(path, '@@ -12,4 +12,9 @@ export const searchRoutes = router();', [
      L('+', "searchRoutes.get('/search', requireSession, async (req, res) => {"),
      L('+', "  const q = String(req.query.q ?? '');"),
      L('+', "  const rows = await db.raw(`SELECT * FROM items WHERE owner_id = ${req.user.id} AND name LIKE '%${q}%'`);"),
      L('+', '  res.json(rows);'),
      L('+', '});'),
    ])
    : file(path, '@@ -1,3 +1,10 @@', [
      L('+', 'def search_payments(db, customer_id: str, q: str):'),
      L('+', '    """Payments of this customer whose description contains q."""'),
      L('+', '    return db.execute('),
      L('+', '        f"SELECT * FROM payments WHERE customer_id = \'{customer_id}\' "'),
      L('+', '        f"AND description LIKE \'%{q}%\'"'),
      L('+', '    ).fetchall()'),
    ]);
  const patch = ts
    ? file(path, '@@ -14,1 +14,1 @@', [
      L('-', "  const rows = await db.raw(`SELECT * FROM items WHERE owner_id = ${req.user.id} AND name LIKE '%${q}%'`);"),
      L('+', "  const rows = await db.raw('SELECT * FROM items WHERE owner_id = ? AND name LIKE ?', [req.user.id, `%${q}%`]);"),
    ])
    : file(path, '@@ -3,4 +3,4 @@', [
      L('-', '        f"SELECT * FROM payments WHERE customer_id = \'{customer_id}\' "'),
      L('-', '        f"AND description LIKE \'%{q}%\'"'),
      L('-', '    ).fetchall()'),
      L('+', '        "SELECT * FROM payments WHERE customer_id = :c AND description LIKE :q",'),
      L('+', '        {"c": customer_id, "q": f"%{q}%"},'),
      L('+', '    ).fetchall()'),
    ]);
  const accepted = commit.verdict === 'fixed';
  const data = repo.components.find(c => c.kind === 'data')?.id ?? serviceId(repo);
  return {
    headline: accepted ? 'Search input was pasted straight into SQL' : 'Search input is pasted straight into SQL — fix not yet accepted',
    summary: accepted
      ? 'The new search built its SQL with string formatting. Probe showed a quote in the search term changed the query in the sandbox. Patch switched to bound parameters and Verify accepted it.'
      : 'The new search builds its SQL with string formatting. Probe confirmed the injection in the sandbox. The candidate patch is waiting on a failing CI job, so Verify has not accepted it yet.',
    seconds: 377, usd: 1.52,
    findings: [{ id: `fnd_${commit.sha.slice(0, 6)}_sqli`, title: 'SQL injection in search', kind: 'security', cwe: 'CWE-89 SQL injection', severity: 'critical', cvss: '8.8', where: `${path} · GET /search` }],
    falseAlarms: [{ on: 'edge', text: 'Search results might be cached at the edge and served to other users' }],
    review: {
      intent: 'Let a signed-in user search their own records by text.',
      expectations: [
        { id: 'exp_owner_scope', text: 'Search returns only the caller\'s own records.', source: 'issue #212, README §Search' },
        { id: 'exp_param_sql', text: 'Queries use bound parameters (repository convention).', source: 'CONTRIBUTING.md §Database' },
      ],
      diff: [diff],
      comments: [{ path, line: ts ? 'L14' : 'L4', severity: 'blocker', title: 'User input formatted into SQL', body: 'Both values are interpolated into the query text. Every other query in this repository uses bound parameters. Handed to security.' }],
      tests: [
        { name: 'test_search_finds_matching_description', expectation: 'exp_owner_scope', before: 'pass', after: 'pass' },
        { name: 'test_search_quote_does_not_change_query', expectation: 'exp_param_sql', before: 'fail', after: 'pass' },
      ],
      verdict: 'Matches the intent for normal input; breaks the parameterised-SQL convention. Sent to security.',
    },
    agents: [
      run('scout', { status: 'done', seconds: 44, tokens: 16_800, outcome: 'Raised SQL injection on the new search (H1, with owner bypass through it as H2) and a possible edge-cache leak of search results (H3).', evidence: ['Query text built with string formatting', 'Owner filter present but inside the same string', 'Edge cache rules do not mention the new query string'], steps: [
        { tool: 'intel.changed_symbols', input: `commit ${commit.sha.slice(0, 7)}`, result: '1 new route', ms: 210, outcome: 'ok' },
        { tool: 'intel.taint', input: 'q → db call', result: 'unsanitised flow, 1 hop', ms: 380, outcome: 'ok' },
        { tool: 'intel.entry_points', input: 'edge cache rules for search', result: 'no rule names the new query string', ms: 170, outcome: 'ok', on: 'edge' },
        { tool: 'record.hypothesis', input: 'H1 SQLi, H2 owner bypass, H3 cached results', result: '3 saved', ms: 30, outcome: 'ok' },
      ], handoff: 'Three hypotheses for Probe.' }),
      run('probe', { status: 'done', seconds: 88, tokens: 20_400, outcome: 'Confirmed: a crafted term returned records owned by another fixture user (non-destructive payload only). Refuted the edge-cache leak: search responses are never cached (a false alarm).', evidence: ["q = x' OR '1'='1 → 14 rows across 2 owners", 'Read-only payloads; no writes attempted (policy)'], steps: [
        { tool: 'sandbox.start', input: `${repo.name}@${commit.sha.slice(0, 7)}`, result: 'healthy in 9.0 s', ms: 9_000, outcome: 'ok' },
        { tool: 'http.request', input: 'GET /search?q=coffee as cus_a', result: '200, 2 rows (own)', ms: 34, outcome: 'ok' },
        { tool: 'http.request', input: "GET /search?q=x' OR '1'='1 as cus_a", result: '200, 14 rows, 2 owners', ms: 36, outcome: 'ok' },
        { tool: 'http.request', input: "GET /search?q='; DROP TABLE payments;--", result: 'denied: destructive payloads are blocked by policy', ms: 1, outcome: 'denied' },
        { tool: 'http.request', input: 'the same search as two users, through the edge', result: 'Cache-Control: private, no-store; nothing cached (H3 refuted)', ms: 52, outcome: 'ok', on: 'edge' },
        { tool: 'record.check', input: 'injection.sql, edge.cache', result: 'H1 confirmed, H2 confirmed via H1, H3 refuted', ms: 30, outcome: 'ok' },
      ], handoff: 'Confirmed weakness with request and response.' }),
      run('trace', { status: 'done', seconds: 30, tokens: 7_000, outcome: 'Any signed-in user can read every row in the table behind search.', evidence: ['edge → api → data store', 'Database user has read access to the whole table'], steps: [
        { tool: 'intel.path', input: 'GET /search', result: '3 hops, session only', ms: 240, outcome: 'ok' },
      ], handoff: 'Attack path with impact.' }),
      run('diagnose', { status: 'done', seconds: 26, tokens: 6_100, outcome: 'Root cause: string-built SQL. Use bound parameters like the rest of the codebase.', evidence: ['CVSS 3.1 8.8 High'], steps: [
        { tool: 'score.cvss31', input: 'confirmed check', result: '8.8 High', ms: 20, outcome: 'ok' },
        { tool: 'record.remediation_plan', input: 'RP1', result: 'approved by a person', ms: 25, outcome: 'ok' },
      ], handoff: 'Remediation plan, approved.' }),
      run('patch', { status: 'done', seconds: 52, tokens: 11_900, outcome: 'Rewrote the query with bound parameters in an isolated worktree.', evidence: [`Diff: ${ts ? '+1 −1' : '+3 −3'} in ${path}`], steps: [
        { tool: 'worktree.create', input: 'isolated', result: 'ready', ms: 850, outcome: 'ok' },
        { tool: 'fs.edit', input: path, result: 'parameterised', ms: 45, outcome: 'ok' },
        { tool: 'record.patch_candidate', input: 'PC1', result: 'saved', ms: 30, outcome: 'ok' },
      ], handoff: 'Candidate diff for Verify.' }),
      run('fortify', { status: 'done', seconds: 24, tokens: 5_200, outcome: 'Proposed a lint rule banning formatted SQL strings and a least-privilege database role for search.', evidence: ['Rule: no f-strings / template literals in db calls'], steps: [
        { tool: 'policy.suggest_rule', input: 'parameterised SQL', result: '1 rule', ms: 250, outcome: 'ok' },
      ], handoff: 'Hardening notes.' }),
      accepted
        ? run('verify', { status: 'done', seconds: 81, tokens: 10_300, outcome: 'Accepted: the crafted term now matches literally and returns 0 foreign rows; all tests pass.', evidence: ['Exploit replay: 14 rows → 0 rows', 'Functional: 27 passed'], steps: [
          { tool: 'sandbox.start', input: 'patched build', result: 'healthy', ms: 8_600, outcome: 'ok' },
          { tool: 'sandbox.run_tests', input: 'existing + generated', result: '27 passed', ms: 7_400, outcome: 'ok' },
          { tool: 'record.verification', input: 'PC1', result: 'accepted', ms: 30, outcome: 'ok' },
        ], handoff: 'Pass.' })
        : run('verify', { status: 'done', seconds: 76, tokens: 9_800, outcome: 'Not accepted yet: the exploit is closed, but 1 unrelated CI test fails on this branch, so the build is not clean.', evidence: ['Exploit replay: 14 rows → 0 rows', 'Functional: 26 passed, 1 failed (test_currency_format, pre-existing)'], steps: [
          { tool: 'sandbox.start', input: 'patched build', result: 'healthy', ms: 8_600, outcome: 'ok' },
          { tool: 'sandbox.run_tests', input: 'existing + generated', result: '26 passed, 1 failed', ms: 7_400, outcome: 'ok' },
          { tool: 'record.verification', input: 'PC1', result: 'needs re-check', ms: 30, outcome: 'ok' },
        ], handoff: 'A person needs to look at the failing test before the fix can be accepted.' }),
    ],
    patch,
    defense: {
      watch: watchAll(repo.components, 'healthy', accepted ? { [data]: 'hardened' } : { [data]: 'attention', [serviceId(repo)]: 'checking' }),
      checkedMinutesAgo: checkedAgo(repo.components, commit.minutesAgo),
      recommendation: accepted
        ? { action: 'Raise monitoring', target: repo.components.find(c => c.id === data)!.label, why: 'Watch query volume on search for a day after the fix.', confidence: 0.69 }
        : { action: 'Rate-limit', target: repo.components.find(c => c.id === serviceId(repo))!.label, why: 'An unaccepted SQL injection fix is open on this service. Slowing search reduces exposure until it is verified.', confidence: 0.77 },
      events: [
        { minutesAgo: 3, text: accepted ? 'Verify accepted the parameterised query' : 'Verify is waiting on a failing CI test', tone: accepted ? 'ok' : 'warn' },
        { minutesAgo: 8, text: 'Probe confirmed SQL injection in search (read-only payload)', tone: 'warn' },
        { minutesAgo: commit.minutesAgo, text: `Push to ${commit.branch} started a check`, tone: 'info' },
      ],
    },
  };
}

// ---------------------------------------------------------------- clean and dependency

/** The release before `version`: 2.12.4 → 2.12.3, 1.47 → 1.46, 5.0 → 4.9. */
export function previousVersion(version: string): string {
  const parts = version.split('.').map(Number);
  for (let i = parts.length - 1; i >= 0; i--) {
    if (parts[i]! > 0) { parts[i]! -= 1; return parts.map((n, j) => (j > i && n === 0 ? 9 : n)).join('.'); }
  }
  return version;
}

/** A small, ordinary diff in the repository's language, named after the commit. */
function cleanDiff(lang: Lang, commit: DemoCommit): DiffFile {
  const slug = commit.message.replace(/^\w+(\([^)]*\))?: /, '').toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '').slice(0, 40);
  if (lang === 'ts') {
    return file(`src/__tests__/${slug.replace(/_/g, '-')}.test.ts`, '@@ -0,0 +1,9 @@', [
      L('+', "import { describe, expect, it } from 'vitest';"),
      L('+', "import { render } from '../test-utils';"),
      L('+', ''),
      L('+', `describe('${slug.replace(/_/g, ' ')}', () => {`),
      L('+', "  it('keeps the existing behaviour', async () => {"),
      L('+', '    const view = await render();'),
      L('+', '    expect(view.errors).toEqual([]);'),
      L('+', '  });'),
      L('+', '});'),
    ]);
  }
  if (lang === 'rs') {
    return file('src/ingest.rs', '@@ -88,6 +88,10 @@ impl Batch {', [
      L(' ', '    pub fn decode(bytes: &[u8]) -> Result<Self, IngestError> {'),
      L('+', '        if bytes.starts_with(&[0x1f, 0x8b]) {'),
      L('+', '            let raw = gunzip(bytes).map_err(IngestError::Compression)?;'),
      L('+', '            return Self::decode(&raw);'),
      L('+', '        }'),
      L(' ', '        serde_json::from_slice(bytes).map_err(IngestError::Json)'),
      L(' ', '    }'),
    ]);
  }
  return file(`tests/test_${slug}.py`, '@@ -0,0 +1,8 @@', [
    L('+', 'from fastapi.testclient import TestClient'),
    L('+', ''),
    L('+', ''),
    L('+', `def test_${slug}(client: TestClient, token_a: str) -> None:`),
    L('+', '    response = client.get("/me", headers={"Authorization": f"Bearer {token_a}"})'),
    L('+', '    assert response.status_code == 200'),
    L('+', '    assert response.json()["id"] == "cus_a"'),
  ]);
}

const MANIFEST: Record<Lang, string> = { py: 'pyproject.toml', ts: 'package.json', rs: 'Cargo.toml' };

function quiet(repo: DemoRepo, commit: DemoCommit, dependency: boolean): Analysis {
  const lang = langOf(repo);
  const dep = commit.message.replace(/^chore\(deps\): bump /, '').split(' to ');
  const prev = previousVersion(dep[1] ?? '1.0.0');
  const diff = dependency
    ? file(MANIFEST[lang], '@@ -14,3 +14,3 @@', [
      L(' ', lang === 'py' ? 'dependencies = [' : lang === 'ts' ? '  "dependencies": {' : '[dependencies]'),
      L('-', lang === 'py' ? `    "${dep[0]}==${prev}",` : lang === 'ts' ? `    "${dep[0]}": "${prev}",` : `${dep[0]} = "${prev}"`),
      L('+', lang === 'py' ? `    "${dep[0]}==${dep[1] ?? 'latest'}",` : lang === 'ts' ? `    "${dep[0]}": "${dep[1] ?? 'latest'}",` : `${dep[0]} = "${dep[1] ?? 'latest'}"`),
    ])
    : cleanDiff(lang, commit);
  const svc = serviceId(repo);
  return {
    headline: dependency ? 'Dependency update: no reachable advisory' : 'No problems found in this change',
    summary: dependency
      ? 'The bumped package has no known advisory affecting the code paths this repository uses. Security agents had nothing to confirm, so the repair agents did not run.'
      : 'The change matches its intent and the reviewer found no broken expectation. Scout raised one low-likelihood hypothesis and Probe refuted it, so the repair agents did not run.',
    seconds: dependency ? 74 : 131, usd: dependency ? 0.18 : 0.41,
    findings: [],
    review: {
      intent: commit.message.replace(/^\w+(\([^)]*\))?: /, ''),
      expectations: [{ id: 'exp_existing_behaviour', text: 'Existing behaviour and tests keep passing.', source: 'test suite' }],
      diff: [diff],
      comments: [],
      tests: [{ name: 'existing suite', expectation: 'exp_existing_behaviour', before: 'pass', after: 'pass' }],
      verdict: 'Matches the intent. No repair needed.',
    },
    agents: [
      run('scout', {
        status: 'done', seconds: dependency ? 18 : 31, tokens: dependency ? 6_100 : 11_400,
        outcome: dependency ? 'Checked the advisory database for the new version: 0 advisories affect used functions.' : 'One low-likelihood hypothesis on the changed code.',
        evidence: dependency ? [`${dep[0]} ${dep[1] ?? ''}: 0 open advisories`, 'Lockfile hash matches the published release'] : ['Changed code is behind the existing auth and ownership checks'],
        steps: dependency
          ? [{ tool: 'deps.advisories', input: `${dep[0]}@${dep[1] ?? 'latest'}`, result: '0 advisories', ms: 640, outcome: 'ok' }, { tool: 'deps.verify_lock', input: MANIFEST[lang], result: 'hash matches', ms: 210, outcome: 'ok' }]
          : [{ tool: 'intel.changed_symbols', input: `commit ${commit.sha.slice(0, 7)}`, result: '1 function changed', ms: 190, outcome: 'ok' }, { tool: 'record.hypothesis', input: 'H1 input validation', result: 'saved (low)', ms: 30, outcome: 'ok' }],
        handoff: dependency ? 'Nothing to test.' : 'One low-likelihood hypothesis.',
      }),
      dependency ? skipped('probe', 'No hypothesis to test.') : run('probe', {
        status: 'done', seconds: 52, tokens: 9_300, outcome: 'Refuted: malformed input is rejected with 422 as expected.', evidence: ['3 malformed requests → 422'],
        steps: [
          { tool: 'sandbox.start', input: `${repo.name}@${commit.sha.slice(0, 7)}`, result: 'healthy', ms: 8_000, outcome: 'ok' },
          { tool: 'http.request', input: 'malformed payloads ×3', result: '422 ×3', ms: 95, outcome: 'ok' },
          { tool: 'record.check', input: 'input_validation', result: 'refuted', ms: 30, outcome: 'ok' },
        ], handoff: 'Refuted. Nothing confirmed.',
      }),
      skipped('trace', 'Nothing was confirmed, so there is no path to follow.'),
      skipped('diagnose', 'Nothing was confirmed.'),
      skipped('patch', 'No approved remediation plan.'),
      skipped('fortify', 'No finding to harden against.'),
      skipped('verify', 'No candidate fix to verify.'),
    ],
    patch: null,
    defense: {
      watch: watchAll(repo.components, 'healthy', { [svc]: commit.minutesAgo < 60 ? 'checking' : 'healthy' }),
      checkedMinutesAgo: checkedAgo(repo.components, commit.minutesAgo),
      recommendation: { action: 'Keep watching', target: 'All components', why: 'No confirmed weakness and no anomaly above the threshold. The defender takes no disruptive action.', confidence: 0.91 },
      events: [
        { minutesAgo: 1, text: 'Routine re-check of all components: healthy', tone: 'ok' },
        { minutesAgo: commit.minutesAgo, text: `Push to ${commit.branch} started a check`, tone: 'info' },
      ],
    },
  };
}

const BUILDERS: Record<ScenarioId, (repo: DemoRepo, commit: DemoCommit) => Analysis> = {
  authz,
  refund,
  injection,
  clean: (repo, commit) => quiet(repo, commit, false),
  dependency: (repo, commit) => quiet(repo, commit, true),
};

export function analyze(repo: DemoRepo, commit: DemoCommit): Analysis {
  return BUILDERS[commit.scenario](repo, commit);
}

/** Every tool step of the run in orchestrator order, for the replay playhead. */
export function replaySteps(analysis: Analysis): { agent: AgentId; index: number }[] {
  return analysis.agents.flatMap(agent => agent.steps.map((_, index) => ({ agent: agent.agent, index })));
}
