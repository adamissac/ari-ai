import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import RealCommitPage from '@/app/(console)/connect/[org]/[repo]/commit/[sha]/page';

vi.mock('next/navigation', () => ({ useParams: () => ({ org: 'test-team', repo: 'test-app', sha: 'c'.repeat(40) }) }));
vi.mock('@/lib/real-repo', () => ({ useAccessibleRepo: () => ({ status: 'ready', data: { connected_repo_id: 'repo_test', full_name: 'test-team/test-app', default_branch: 'main' } }) }));
vi.mock('@/lib/use-resource', () => ({ useResource: () => ({ status: 'ready', data: { items: [{ sha: 'c'.repeat(40) }] } }) }));
vi.mock('@/lib/simulated-attack', () => ({ simulatedAttack: () => null }));
vi.mock('@/components/demo/commit-analysis', () => ({ CommitAnalysis: () => null }));

afterEach(cleanup);

it('distinguishes real GitHub commit metadata from illustrative analysis', () => {
  render(<RealCommitPage />);
  const badge = screen.getByTestId('real-commit-provenance');
  expect(badge.textContent).toBe('Illustrative analysis · real commit');
  expect(badge.title).toContain('Commit metadata comes from GitHub');
  expect(badge.title).toContain('illustrative replay, not a live assessment');
  expect(badge.title).not.toContain('No repository is accessed');
  expect(screen.queryByTestId('demo-marker')).toBeNull();
});
