import { cleanup, render, screen } from '@testing-library/react';
import type { Project, Repository } from '@hackatl/frontend-transport';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import SetupPage from '@/app/(console)/projects/[projectId]/setup/page';

const mocks = vi.hoisted(() => ({
  query: 'repo=rep_12345678&step=5',
  useResource: vi.fn(),
  project: null as unknown,
  replace: vi.fn(),
  push: vi.fn(),
}));
vi.mock('@/components/project', () => ({ useProject: () => mocks.project }));
vi.mock('@/lib/use-resource', () => ({ useResource: mocks.useResource }));
vi.mock('next/navigation', () => ({
  useSearchParams: () => new URLSearchParams(mocks.query),
  usePathname: () => '/projects/prj_12345678/setup',
  useRouter: () => ({ replace: mocks.replace, push: mocks.push }),
}));

const project = {
  id: 'prj_12345678',
  name: 'Payments',
  settings: {
    review: { strictness: 2, review_pushes: false, review_pull_requests: false, comment_on_pull_requests: false },
    monitoring_policy: { enabled: false },
    delivery_mode: 'pull_request',
  },
} as unknown as Project;
const repo = {
  id: 'rep_12345678',
  full_name: 'acme/payments-lite',
  default_branch: 'main',
  installation_id: null,
} as unknown as Repository;

beforeEach(() => {
  localStorage.clear();
  mocks.query = 'repo=rep_12345678&step=5';
  mocks.project = { project, reloadProject: vi.fn() };
  mocks.useResource.mockImplementation((key: string | null) => {
    if (key?.includes('setup-repos')) return { status: 'ready', data: { items: [repo] }, reload: vi.fn() };
    if (key?.includes('setup-scopes')) return { status: 'ready', data: { items: [] }, reload: vi.fn() };
    if (key?.includes('setup-runs')) return { status: 'ready', data: { items: [] }, reload: vi.fn() };
    return { status: 'ready', data: { items: [] }, reload: vi.fn() };
  });
});
afterEach(cleanup);

it('resumes the testing-scope panel from ?step=5', () => {
  render(<SetupPage />);
  expect(screen.getByTestId('setup-step-5')).toBeTruthy();
  expect(screen.getByRole('button', { name: 'Approve sandbox testing for 7 days' })).toBeTruthy();
});

it('disables Start until the testing scope is authorized', () => {
  mocks.query = 'repo=rep_12345678&step=7';
  render(<SetupPage />);
  expect(screen.getByTestId('setup-step-7')).toBeTruthy();
  expect(screen.getByRole('button', { name: 'Start first assessment' }).hasAttribute('disabled')).toBe(true);
  expect(screen.getByRole('button', { name: 'Review step 5: testing scope' })).toBeTruthy();
});
