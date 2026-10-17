/**
 * Simulated demo (ADR 0013). Every value in this module is illustrative: the accounts,
 * organisations, repositories, commits, agent runs and review results are written by hand
 * so the product can be shown without a backend, GitHub App or model key. The pages that use
 * it always carry a visible "Simulated demo" marker and never mix these values with records.
 *
 * The two security and functional stories are modelled on the project's own planted-defect
 * target (examples/payments-lite): an ownership check missing on GET /payments/{id} (CWE-639)
 * and a refund bound that compares only the new refund (CWE-840).
 */

export type Verdict = 'fixed' | 'clean' | 'needs_review' | 'running';
export type CheckState = 'passing' | 'failing' | 'pending';

export interface DemoUser { login: string; name: string }
export interface DemoOrg { login: string; name: string; kind: 'organization' | 'personal'; members: number; plan: string }
export interface DemoRepo {
  org: string;
  name: string;
  description: string;
  language: string;
  visibility: 'private' | 'internal' | 'public';
  defaultBranch: string;
  stars: number;
  /** Components watched by continuous defense, in dependency order. */
  components: DemoComponent[];
  links: [string, string][];
  /** Commits newest first. */
  commits: DemoCommit[];
}
export interface DemoComponent { id: string; label: string; kind: string; critical: boolean }
export interface DemoCommit {
  sha: string;
  message: string;
  body: string;
  author: string;
  /** Minutes before "now" when the commit was pushed. */
  minutesAgo: number;
  branch: string;
  ci: CheckState;
  verdict: Verdict;
  scenario: ScenarioId;
  files: number;
  additions: number;
  deletions: number;
}

export type ScenarioId = 'authz' | 'refund' | 'clean' | 'injection' | 'dependency';

export const DEMO_USER: DemoUser = { login: 'akshar-koth', name: 'Akshar Koth' };

export const DEMO_ORGS: DemoOrg[] = [
  { login: 'lumen-pay', name: 'Lumen Pay', kind: 'organization', members: 48, plan: 'Enterprise' },
  { login: 'harbor-labs', name: 'Harbor Labs', kind: 'organization', members: 17, plan: 'Team' },
  { login: DEMO_USER.login, name: DEMO_USER.name, kind: 'personal', members: 1, plan: 'Personal' },
];

/** The demo account belongs to Akshar Koth at Lumen Pay: only that organization is connected. */
export const ACCOUNT_ORGS: DemoOrg[] = DEMO_ORGS.filter(o => o.login === 'lumen-pay');
/** When Lumen Pay connected Ari (before the oldest commit shown). */
export const CONNECTED_DAYS_AGO = 7;

const AUTHORS = ['akshar-koth', 'mina-okafor', 'jules-park', 'devon-shah', 'sam-lindqvist', 'priya-natarajan'];

/** Stable 40-hex pseudo SHA so links and labels never change between renders. */
export function demoSha(seed: string): string {
  let out = '';
  let h = 0x811c9dc5;
  for (let round = 0; out.length < 40; round++) {
    for (const ch of `${seed}:${round}`) {
      h ^= ch.charCodeAt(0);
      h = Math.imul(h, 0x01000193) >>> 0;
    }
    out += h.toString(16).padStart(8, '0');
  }
  return out.slice(0, 40);
}

type CommitSeed = Omit<DemoCommit, 'sha' | 'author'> & { author?: string };

function commits(repo: string, seeds: CommitSeed[]): DemoCommit[] {
  return seeds.map((seed, i) => ({
    ...seed,
    author: seed.author ?? AUTHORS[(i * 5 + repo.length) % AUTHORS.length]!,
    sha: demoSha(`${repo}/${i}/${seed.message}`),
  }));
}

const PAYMENTS_COMPONENTS: DemoComponent[] = [
  { id: 'edge', label: 'Edge gateway', kind: 'edge', critical: false },
  { id: 'api', label: 'payments-api', kind: 'service', critical: true },
  { id: 'auth', label: 'Auth service', kind: 'identity', critical: true },
  { id: 'refunds', label: 'Refund worker', kind: 'worker', critical: false },
  { id: 'db', label: 'Ledger DB', kind: 'data', critical: true },
  { id: 'logs', label: 'Audit log', kind: 'logging', critical: false },
];
const PAYMENTS_LINKS: [string, string][] = [['edge', 'api'], ['api', 'auth'], ['api', 'refunds'], ['api', 'db'], ['refunds', 'db'], ['api', 'logs']];

const WEB_COMPONENTS: DemoComponent[] = [
  { id: 'cdn', label: 'CDN', kind: 'edge', critical: false },
  { id: 'site', label: 'checkout-web', kind: 'site', critical: true },
  { id: 'bff', label: 'Checkout BFF', kind: 'service', critical: true },
  { id: 'auth', label: 'Session auth', kind: 'identity', critical: true },
  { id: 'logs', label: 'RUM + logs', kind: 'logging', critical: false },
];
const WEB_LINKS: [string, string][] = [['cdn', 'site'], ['site', 'bff'], ['bff', 'auth'], ['site', 'logs']];

const FLEET_COMPONENTS: DemoComponent[] = [
  { id: 'edge', label: 'Ingress', kind: 'edge', critical: false },
  { id: 'portal', label: 'fleet-portal', kind: 'site', critical: false },
  { id: 'api', label: 'Fleet API', kind: 'service', critical: true },
  { id: 'sso', label: 'SSO', kind: 'identity', critical: true },
  { id: 'db', label: 'Postgres', kind: 'data', critical: true },
  { id: 'agents', label: 'Device agents', kind: 'endpoints', critical: false },
];
const FLEET_LINKS: [string, string][] = [['edge', 'portal'], ['portal', 'api'], ['api', 'sso'], ['api', 'db'], ['agents', 'api']];

export const DEMO_REPOS: DemoRepo[] = [
  {
    org: 'lumen-pay', name: 'payments-api', language: 'Python', visibility: 'private', defaultBranch: 'main', stars: 41,
    description: 'Card payments, refunds and customer ledger API (FastAPI).',
    components: PAYMENTS_COMPONENTS, links: PAYMENTS_LINKS,
    commits: commits('payments-api', [
      { message: 'feat(payments): add GET /payments/{payment_id} lookup', body: 'Support agents and the mobile app need to fetch a single payment by id.', minutesAgo: 14, branch: 'feat/payment-lookup', ci: 'passing', verdict: 'fixed', scenario: 'authz', files: 3, additions: 64, deletions: 2 },
      { message: 'feat(refunds): allow partial refunds', body: 'Customers can now refund part of a payment in several steps.', minutesAgo: 95, branch: 'main', ci: 'passing', verdict: 'fixed', scenario: 'refund', files: 4, additions: 88, deletions: 19 },
      { message: 'chore(deps): bump pydantic to 2.12.4', body: 'Routine dependency update.', minutesAgo: 260, branch: 'main', ci: 'passing', verdict: 'clean', scenario: 'dependency', files: 2, additions: 3, deletions: 3 },
      { message: 'fix(customers): return 404 for unknown customer ids', body: '', minutesAgo: 410, branch: 'main', ci: 'passing', verdict: 'clean', scenario: 'clean', files: 2, additions: 12, deletions: 4 },
      { message: 'feat(search): filter payments by description', body: 'Adds a ?q= filter to GET /payments.', minutesAgo: 1290, branch: 'main', ci: 'passing', verdict: 'fixed', scenario: 'injection', files: 3, additions: 41, deletions: 6 },
      { message: 'refactor(store): extract refunds_for helper', body: '', minutesAgo: 1715, branch: 'main', ci: 'passing', verdict: 'clean', scenario: 'clean', files: 2, additions: 22, deletions: 17 },
      { message: 'test: cover currency validation edge cases', body: '', minutesAgo: 2890, branch: 'main', ci: 'passing', verdict: 'clean', scenario: 'clean', files: 1, additions: 48, deletions: 0 },
      { message: 'docs: document the require_owner convention', body: '', minutesAgo: 4320, branch: 'main', ci: 'passing', verdict: 'clean', scenario: 'clean', files: 2, additions: 19, deletions: 1 },
    ]),
  },
  {
    org: 'lumen-pay', name: 'checkout-web', language: 'TypeScript', visibility: 'private', defaultBranch: 'main', stars: 23,
    description: 'Hosted checkout pages and the checkout backend-for-frontend.',
    components: WEB_COMPONENTS, links: WEB_LINKS,
    commits: commits('checkout-web', [
      { message: 'feat(orders): show order history to signed-in shoppers', body: '', minutesAgo: 38, branch: 'main', ci: 'passing', verdict: 'fixed', scenario: 'authz', files: 5, additions: 132, deletions: 11 },
      { message: 'fix(cart): keep coupon after currency switch', body: '', minutesAgo: 520, branch: 'main', ci: 'passing', verdict: 'clean', scenario: 'clean', files: 2, additions: 14, deletions: 6 },
      { message: 'chore(deps): bump next to 16.4.2', body: '', minutesAgo: 1460, branch: 'main', ci: 'passing', verdict: 'clean', scenario: 'dependency', files: 2, additions: 4, deletions: 4 },
      { message: 'feat(search): server-side product search', body: '', minutesAgo: 3010, branch: 'main', ci: 'failing', verdict: 'needs_review', scenario: 'injection', files: 4, additions: 77, deletions: 9 },
      { message: 'style: tighten checkout summary spacing', body: '', minutesAgo: 5100, branch: 'main', ci: 'passing', verdict: 'clean', scenario: 'clean', files: 3, additions: 21, deletions: 25 },
    ]),
  },
  {
    org: 'lumen-pay', name: 'ledger-service', language: 'Python', visibility: 'internal', defaultBranch: 'main', stars: 12,
    description: 'Double-entry ledger and settlement batches.',
    components: PAYMENTS_COMPONENTS, links: PAYMENTS_LINKS,
    commits: commits('ledger-service', [
      { message: 'feat(settlement): nightly batch reversal endpoint', body: '', minutesAgo: 180, branch: 'main', ci: 'passing', verdict: 'fixed', scenario: 'refund', files: 4, additions: 96, deletions: 8 },
      { message: 'perf(ledger): index entries by account and day', body: '', minutesAgo: 1990, branch: 'main', ci: 'passing', verdict: 'clean', scenario: 'clean', files: 3, additions: 30, deletions: 2 },
      { message: 'chore(deps): bump sqlalchemy to 2.0.44', body: '', minutesAgo: 6200, branch: 'main', ci: 'passing', verdict: 'clean', scenario: 'dependency', files: 2, additions: 3, deletions: 3 },
    ]),
  },
  {
    org: 'harbor-labs', name: 'fleet-portal', language: 'TypeScript', visibility: 'private', defaultBranch: 'main', stars: 9,
    description: 'Device fleet admin portal and API.',
    components: FLEET_COMPONENTS, links: FLEET_LINKS,
    commits: commits('fleet-portal', [
      { message: 'feat(devices): per-device detail endpoint', body: '', minutesAgo: 62, branch: 'main', ci: 'passing', verdict: 'fixed', scenario: 'authz', files: 4, additions: 71, deletions: 3 },
      { message: 'feat(audit): export audit trail as CSV', body: '', minutesAgo: 840, branch: 'main', ci: 'passing', verdict: 'fixed', scenario: 'injection', files: 3, additions: 55, deletions: 4 },
      { message: 'fix(sso): refresh tokens before expiry', body: '', minutesAgo: 2400, branch: 'main', ci: 'passing', verdict: 'clean', scenario: 'clean', files: 2, additions: 18, deletions: 7 },
    ]),
  },
  {
    org: 'harbor-labs', name: 'telemetry-ingest', language: 'Rust', visibility: 'private', defaultBranch: 'main', stars: 5,
    description: 'High-volume device telemetry ingestion.',
    components: FLEET_COMPONENTS, links: FLEET_LINKS,
    commits: commits('telemetry-ingest', [
      { message: 'feat(ingest): accept gzip batches', body: '', minutesAgo: 300, branch: 'main', ci: 'passing', verdict: 'clean', scenario: 'clean', files: 3, additions: 64, deletions: 12 },
      { message: 'chore(deps): bump tokio to 1.47', body: '', minutesAgo: 4100, branch: 'main', ci: 'passing', verdict: 'clean', scenario: 'dependency', files: 2, additions: 3, deletions: 3 },
    ]),
  },
  {
    org: DEMO_USER.login, name: 'refund-calculator', language: 'Python', visibility: 'public', defaultBranch: 'main', stars: 2,
    description: 'Weekend project: refund policy calculator.',
    components: PAYMENTS_COMPONENTS.slice(0, 3), links: [['edge', 'api'], ['api', 'auth']],
    commits: commits('refund-calculator', [
      { message: 'feat: partial refund support', body: '', minutesAgo: 720, branch: 'main', ci: 'passing', verdict: 'fixed', scenario: 'refund', files: 2, additions: 40, deletions: 5, author: DEMO_USER.login },
      { message: 'init', body: '', minutesAgo: 9000, branch: 'main', ci: 'passing', verdict: 'clean', scenario: 'clean', files: 6, additions: 210, deletions: 0, author: DEMO_USER.login },
    ]),
  },
];

export function reposFor(org: string): DemoRepo[] {
  return DEMO_REPOS.filter(repo => repo.org === org);
}

export function findRepo(org: string, name: string): DemoRepo | undefined {
  return DEMO_REPOS.find(repo => repo.org === org && repo.name === name);
}

export function findCommit(repo: DemoRepo, sha: string): DemoCommit | undefined {
  return repo.commits.find(commit => commit.sha === sha || commit.sha.startsWith(sha));
}

export function relativeTime(minutesAgo: number): string {
  if (minutesAgo < 1) return 'just now';
  if (minutesAgo < 60) return `${minutesAgo} min ago`;
  const hours = Math.round(minutesAgo / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? '' : 's'} ago`;
  const days = Math.round(hours / 24);
  return `${days} day${days === 1 ? '' : 's'} ago`;
}

export const VERDICT: Record<Verdict, { label: string; tone: 'ok' | 'warn' | 'bad' | 'info' }> = {
  fixed: { label: 'Issue found · fix verified', tone: 'ok' },
  clean: { label: 'No issues', tone: 'ok' },
  needs_review: { label: 'Needs review', tone: 'warn' },
  running: { label: 'Analyzing', tone: 'info' },
};
