import { cleanup, render, screen, within } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import OnboardingPage from '@/app/(console)/projects/[projectId]/onboarding/page';

const mocks = vi.hoisted(() => ({ useResource: vi.fn() }));
vi.mock('@/lib/use-resource', () => ({ useResource: mocks.useResource }));
vi.mock('@/lib/api', () => ({ api: () => ({}) }));
vi.mock('@/components/project', () => ({
  useProject: () => ({
    project: { id: 'prj_1', name: 'Payments' },
    selectedRepo: { id: 'rep_1', full_name: 'acme/pay', disconnected: false },
  }),
}));
afterEach(cleanup);

const step = (id: string, state = 'done') => ({ id, state, detail: id, subject_id: null });

it('counts code-review steps plus server-saved setup and keeps Defense Lab optional', () => {
  mocks.useResource.mockImplementation((key: string | null) => key?.startsWith('onboarding-setup')
    ? { status: 'ready', data: { complete: true }, reload: vi.fn() }
    : { status: 'ready', reload: vi.fn(), data: { steps: [
      step('sign_in'), step('organization'), step('repository'), step('github_access'), step('snapshot', 'todo'), step('scope'),
      step('application', 'todo'), step('deploy_mapping', 'blocked'), step('monitoring', 'todo'), step('test_event', 'blocked'), step('evidence', 'blocked'),
    ] } });
  render(<OnboardingPage />);
  expect(screen.getByTestId('onboarding-progress').textContent).toContain('Code review: 6 of 7 steps');
  expect(screen.getByTestId('onboarding-step-setup').getAttribute('data-state')).toBe('done');
  const optional = screen.getByTestId('onboarding-optional-steps');
  expect(within(optional).getByTestId('onboarding-step-application')).toBeTruthy();
  expect(within(screen.getByTestId('onboarding-steps')).queryByTestId('onboarding-step-application')).toBeNull();
});
