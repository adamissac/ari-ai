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

export function simulatedAttack(fullName: string, defaultBranch: string): SimulatedAttack {
  const [owner = fullName, name = fullName] = fullName.split('/');
  const seed = demoSha(fullName);
  const scenario = ATTACKS[parseInt(seed.slice(0, 2), 16) % ATTACKS.length]!;
  const template = DEMO_REPOS.find(r => r.commits.some(c => c.scenario === scenario))!;
  const base = template.commits.find(c => c.scenario === scenario)!;
  const commit: DemoCommit = {
    ...base,
    sha: seed,
    message: `Simulated attack on ${fullName}`,
    body: `Probe attempted ${ATTACK_NAME[scenario]} against an illustrative service; Patch, Fortify and Verify closed it.`,
    author: 'ari-red-team',
    minutesAgo: 0,
    branch: defaultBranch,
  };
  return {
    repo: { ...template, org: owner, name, defaultBranch, commits: [commit] },
    commit,
    attack: ATTACK_NAME[scenario],
  };
}
