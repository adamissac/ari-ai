import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { CommitAnalysis } from '@/components/demo/commit-analysis';
import type { DemoCommit, DemoRepo } from '@/lib/demo/data';
import { AGENT_ORDER, type Analysis } from '@/lib/demo/scenarios';

beforeEach(() => { vi.stubGlobal('matchMedia', (q: string) => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

const commit: DemoCommit = {
  sha: 'a'.repeat(40), message: 'Add invoice lookup', body: '', author: 'octocat', minutesAgo: 5, branch: 'main',
  ci: 'pending', verdict: 'needs_review', scenario: 'clean', files: 1, additions: 3, deletions: 1,
};
const repo: DemoRepo = {
  org: 'octo', name: 'shop', description: '', language: '', visibility: 'public', defaultBranch: 'main', stars: 0,
  components: [{ id: 'api', label: 'API', kind: 'service', critical: true }, { id: 'db', label: 'Database', kind: 'data', critical: true }],
  links: [['api', 'db']], commits: [commit],
};
const analysis: Analysis = {
  headline: 'Anyone can read any invoice', summary: 'The new route skips the owner check.', seconds: 61, usd: 0.31,
  findings: [{ id: 'f1', title: 'Missing ownership check', kind: 'security', cwe: 'CWE-639', severity: 'high', cvss: '7.5', where: 'api/invoices.py:12', on: 'service' }],
  falseAlarms: [{ on: 'data', text: 'Query is parameterised' }],
  review: {
    intent: 'Adds GET /invoices/{id}.',
    expectations: [{ id: 'e1', text: 'Users only see their own invoices', source: 'api/invoices.py:12' }],
    diff: [{ path: 'api/invoices.py', additions: 3, deletions: 1, hunks: [{ header: '@@ -10,2 +10,4 @@', lines: [{ kind: '+', text: 'return db.get(id)' }] }] }],
    comments: [{ path: 'api/invoices.py', line: 'L12', severity: 'blocker', title: 'No owner check', body: 'Compare invoice.owner to the caller.' }],
    tests: [{ name: 'test_other_user_gets_404', expectation: 'e1', before: 'fail', after: 'pass' }],
    verdict: 'Do not merge until the owner check is added.',
  },
  agents: AGENT_ORDER.map(role => ({
    ...role, status: 'done', outcome: `${role.label} done`, evidence: [], handoff: '', seconds: 0, tokens: 0,
    steps: [{ tool: 'intel.changed_symbols', input: 'api/invoices.py', result: 'get_invoice', ms: 0, outcome: 'ok', on: 'service' }],
  })),
  patch: { path: 'api/invoices.py', additions: 1, deletions: 0, hunks: [{ header: '@@ -12 +12,2 @@', lines: [{ kind: '+', text: 'if inv.owner != user.id: raise NotFound()' }] }] },
  defense: { watch: {}, checkedMinutesAgo: {}, recommendation: { action: 'rule', target: 'api', why: 'x', confidence: 0 }, events: [] },
};
const live = { model: 'claude-opus-5-5', truncated: false, htmlUrl: 'https://github.com/octo/shop/commit/' + 'a'.repeat(40) };

it('renders a live analysis through every tab without claiming execution', () => {
  render(<CommitAnalysis repo={repo} commit={commit} analysis={analysis} live={live} />);
  fireEvent.click(screen.getByTestId('demo-skip'));
  expect(screen.getByTestId('demo-result').textContent).toContain('Anyone can read any invoice');
  expect(screen.getByText('View on GitHub').getAttribute('href')).toBe(live.htmlUrl);
  fireEvent.click(screen.getByTestId('demo-tab-review'));
  const review = screen.getByTestId('demo-review').textContent!;
  expect(review).toContain('Proposed fix');
  expect(review).toContain('not applied, not tested');
  expect(review).toContain('should pass');
  expect(review).toContain('not run yet');
  fireEvent.click(screen.getByTestId('demo-tab-agents'));
  expect(document.body.textContent).toContain('API');
});
