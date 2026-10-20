import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import RealCommitPage from '@/app/(console)/connect/[org]/[repo]/commit/[sha]/page';

vi.mock('next/navigation', () => ({ useParams: () => ({ org: 'test-team', repo: 'test-app', sha: 'c'.repeat(40) }) }));
vi.mock('@/lib/real-repo', () => ({ useAccessibleRepo: () => ({ status: 'ready', data: { connected_repo_id: 'repo_test', full_name: 'test-team/test-app', default_branch: 'main', private: false } }) }));
vi.mock('@/lib/api', () => ({ api: () => ({ repositoryCommits: async () => ({ items: [{ sha: 'c'.repeat(40), message: 'Selected change', html_url: 'https://git.example/team/app/commit/selected' }], available: true, reason: null }) }) }));
vi.mock('@/components/demo/commit-analysis', () => ({ CommitAnalysis: () => null }));
vi.mock('@/components/real-assessment-panel', () => ({ RealAssessmentPanel: () => null }));

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it('labels the Claude call as a narrated preview, and asks the analyze route for this commit', async () => {
  const fetchMock = vi.fn(async () => new Response(JSON.stringify({ error: { message: 'not configured' } }), { status: 503 }));
  vi.stubGlobal('fetch', fetchMock);
  render(<RealCommitPage />);
  expect(fetchMock).not.toHaveBeenCalled();
  fireEvent.click(screen.getByText('Optional quick read'));
  fireEvent.click(screen.getByRole('button', { name: 'Read this diff' }));
  const badge = screen.getByTestId('real-commit-provenance');
  expect(badge.textContent).toBe('Quick read · nothing executed');
  expect(badge.title).toContain('The diff comes from GitHub');
  expect(fetchMock).toHaveBeenCalledWith('/api/analyze', expect.objectContaining({ method: 'POST', body: JSON.stringify({ repo: 'test-team/test-app', sha: 'c'.repeat(40) }) }));
  await waitFor(() => expect(screen.getByRole('alert').textContent).toContain('not configured'));
});

it('uses the configured provider commit URL rather than assuming GitHub.com', async () => {
  render(<RealCommitPage />);
  expect((await screen.findByRole('link', { name: /View commit on GitHub/ })).getAttribute('href')).toBe('https://git.example/team/app/commit/selected');
});
