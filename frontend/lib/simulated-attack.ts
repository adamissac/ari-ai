import { DEMO_REPOS, demoSha, type DemoCommit, type DemoRepo } from '@/lib/demo/data';

/**
 * A labelled, illustrative attack replay for a real repository whose code cannot be
 * attacked live (live attacks need a Python ASGI service in the sandbox). It reuses the
 * simulated demo's scenarios (ADR 0013): nothing in the repository is read or attacked,
 * and every page that renders it says so.
 */
const ATTACKS = ['authz', 'injection', 'refund'] as const;

export interface SimulatedAttack { repo: DemoRepo; commit: DemoCommit; attack: string }

const ATTACK_NAME: Record<(typeof ATTACKS)[number], string> = {
  authz: 'broken object-level authorization (IDOR)',
  injection: 'SQL injection through a search filter',
  refund: 'a business-logic race on refunds',
};

/** A real commit to frame the replay around (its SHA, message and author are shown as-is). */
export interface RealCommit { sha: string; message: string; author: string; committed_at?: string | null }

export function minutesSince(iso: string | null | undefined, now = Date.now()): number {
  const t = iso ? Date.parse(iso) : NaN;
  return Number.isFinite(t) ? Math.max(0, Math.round((now - t) / 60000)) : 0;
}

export function simulatedAttack(fullName: string, defaultBranch: string, real?: RealCommit): SimulatedAttack {
  const [owner = fullName, name = fullName] = fullName.split('/');
  const seed = demoSha(real ? `${fullName}@${real.sha}` : fullName);
  const scenario = ATTACKS[parseInt(seed.slice(0, 2), 16) % ATTACKS.length]!;
  const template = DEMO_REPOS.find(r => r.commits.some(c => c.scenario === scenario))!;
  const base = template.commits.find(c => c.scenario === scenario)!;
  const commit: DemoCommit = {
    ...base,
    sha: real?.sha ?? seed,
    message: real?.message ?? `Simulated attack on ${fullName}`,
    body: `Probe attempted ${ATTACK_NAME[scenario]} against an illustrative service; Patch, Fortify and Verify closed it.`,
    author: real?.author ?? 'ari-red-team',
    minutesAgo: minutesSince(real?.committed_at),
    branch: defaultBranch,
  };
  return {
    repo: { ...template, org: owner, name, defaultBranch, commits: [commit] },
    commit,
    attack: ATTACK_NAME[scenario],
  };
}
