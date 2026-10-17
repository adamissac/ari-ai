import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import CommitsPage from '@/app/(console)/projects/[projectId]/commits/page';

const state = vi.hoisted(() => ({ status: 'ready', data: { snapshots: { items: [{ id: 's1', commit_sha: 'abc123' }], next_cursor: null }, assessments: { items: [{ id: 'a1', snapshot_id: 's1', state: 'COMPLETED' }, { id: 'a2', snapshot_id: 'other', state: 'COMPLETED' }], next_cursor: null } } }));
vi.mock('@/components/project', () => ({ useProject: () => ({ project: { id: 'p1' }, repos: [{ id: 'r1', full_name: 'team/app', project_id: 'p1' }] }) }));
vi.mock('@/components/repo-commits', () => ({ RepoCommits: ({ onPick }: { onPick: (sha: string) => void }) => <button onClick={() => onPick('abc123')}>Fix payment check</button> }));
vi.mock('@/lib/use-resource', () => ({ useResource: (key: string) => key.startsWith('commit-run:') ? { status: 'ready', data: { items: [] }, reload: vi.fn() } : ({ ...state, reload: vi.fn() }) }));
vi.mock('next/link', () => ({ default: ({ href, children, ...props }: React.PropsWithChildren<{ href: string }>) => <a href={href} {...props}>{children}</a> }));
afterEach(cleanup);
it('opens only the selected commit’s recorded assessment journey', () => {
  render(<CommitsPage />);
  expect(screen.queryByText('Open reviewer & agent journey')).toBeNull();
  fireEvent.click(screen.getByText('Fix payment check'));
  const link = screen.getByText('Open reviewer & agent journey').closest('a');
  expect(link?.getAttribute('href')).toBe('/projects/p1/assessments/a1');
  expect(screen.queryByText('a2')).toBeNull();
  expect(screen.getByText('Analyze this commit').getAttribute('href')).toContain('sha=abc123');
});
