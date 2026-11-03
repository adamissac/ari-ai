import { DEMO_REPOS, type DemoCommit, type ScenarioId } from '@/lib/demo/data';
import { analyze } from '@/lib/demo/scenarios';
import type { LiveResult } from '@/lib/live-analysis';

/** Model label of a demo quick read: a pre-written sample, not a model call. */
export const DEMO_QUICK_READ_MODEL = 'sample';

function scenarioFor(message: string): ScenarioId {
  if (/payments\/\{|lookup|detail endpoint|order history/i.test(message)) return 'authz';
  if (/refund|reversal/i.test(message)) return 'refund';
  if (/search|filter|export/i.test(message)) return 'injection';
  if (/deps|bump/i.test(message)) return 'dependency';
  return 'clean';
}

/**
 * The commit page's quick read for the demo account, built from the sample scenarios in this
 * bundle instead of POST /api/analyze (which reads GitHub and calls Claude). `listed` is the
 * commit row the simulated account returned, for commits that are not in the sample data.
 */
export function demoQuickRead(fullName: string, sha: string, listed?: { message: string; author: string; committed_at: string | null }): LiveResult | null {
  const repo = DEMO_REPOS.find(r => `${r.org}/${r.name}` === fullName);
  if (!repo) return null;
  const known = repo.commits.find(c => c.sha.startsWith(sha) || sha.startsWith(c.sha));
  const commit: DemoCommit | undefined = known ?? (listed ? {
    sha,
    message: listed.message,
    body: '',
    author: listed.author,
    minutesAgo: listed.committed_at ? Math.max(0, Math.round((Date.now() - Date.parse(listed.committed_at)) / 60_000)) : 0,
    branch: repo.defaultBranch,
    ci: 'passing',
    verdict: scenarioFor(listed.message) === 'clean' || scenarioFor(listed.message) === 'dependency' ? 'clean' : 'needs_review',
    scenario: scenarioFor(listed.message),
    files: 3,
    additions: 48,
    deletions: 6,
  } : undefined);
  if (!commit) return null;
  const quiet = commit.scenario === 'clean' || commit.scenario === 'dependency';
  return {
    commit: {
      sha,
      message: commit.message,
      body: commit.body,
      author: commit.author,
      committedAt: new Date(Date.now() - commit.minutesAgo * 60_000).toISOString(),
      htmlUrl: '',
      additions: commit.additions,
      deletions: commit.deletions,
      files: commit.files,
    },
    analysis: analyze(repo, { ...commit, sha }),
    components: repo.components,
    links: repo.links,
    verdict: quiet ? 'clean' : 'needs_review',
    model: DEMO_QUICK_READ_MODEL,
    truncated: false,
    usage: { input_tokens: 0, output_tokens: 0 },
  };
}
