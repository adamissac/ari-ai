import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import RealCommitPage from '@/app/(console)/connect/[org]/[repo]/commit/[sha]/page';

vi.mock('next/navigation', () => ({ useParams: () => ({ org: 'test-team', repo: 'test-app', sha: 'c'.repeat(40) }) }));
vi.mock('@/lib/real-repo', () => ({ useAccessibleRepo: () => ({ status: 'ready', data: { connected_repo_id: 'repo_test', full_name: 'test-team/test-app', default_branch: 'main', private: false } }) }));
vi.mock('@/components/demo/commit-analysis', () => ({ CommitAnalysis: () => null }));

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it('labels the analysis as live and static, and asks the analyze route for this commit', async () => {
  const fetchMock = vi.fn(async () => new Response(JSON.stringify({ error: { message: 'not configured' } }), { status: 503 }));
  vi.stubGlobal('fetch', fetchMock);
  render(<RealCommitPage />);
  const badge = screen.getByTestId('real-commit-provenance');
  expect(badge.textContent).toBe('Live analysis · real commit');
  expect(badge.title).toContain('The diff comes from GitHub');
  expect(screen.getByTestId('real-commit-note').textContent).toContain('no code was run, nothing was attacked');
  expect(fetchMock).toHaveBeenCalledWith('/api/analyze', expect.objectContaining({ method: 'POST', body: JSON.stringify({ repo: 'test-team/test-app', sha: 'c'.repeat(40) }) }));
  await waitFor(() => expect(screen.getByRole('alert').textContent).toContain('not configured'));
});
