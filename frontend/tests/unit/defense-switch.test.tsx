import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import { ApiClient, type MeResponse, type Project, type ProjectSettings } from '@hackatl/frontend-transport';
import { DefenseSwitch } from '@/components/defense-switch';
import { setApiClient } from '@/lib/api';

const settings: ProjectSettings = {
  default_budget: { max_tokens: 400_000, max_usd: 10, max_wall_clock_s: 1800 },
  monitoring_policy: {
    enabled: true,
    min_interval_s: 600,
    ignore_paths_only: ['tests/**', 'docs/**'],
    monitoring_budget: { max_tokens: 150_000, max_usd: 3, max_wall_clock_s: 900 },
  },
  languages: ['python', 'typescript'],
};

const project: Project = {
  id: 'prj_12345678',
  org_id: 'org_12345678',
  name: 'Payments',
  settings,
  created_at: '2026-10-19T00:00:00Z',
};

const session: MeResponse = {
  user: { id: 'usr_12345678', github_login: 'tester', display_name: null, created_at: '2026-10-19T00:00:00Z' },
  memberships: [],
  csrf_token: 'test-csrf',
};

afterEach(() => {
  cleanup();
  setApiClient(undefined);
});

it('renders enabled defense as On', () => {
  render(<DefenseSwitch project={project} />);
  const toggle = screen.getByRole('switch', { name: '24/7 defense' });
  expect(toggle.getAttribute('aria-checked')).toBe('true');
  expect(toggle.textContent).toContain('On');
  expect(screen.getByText('Watching every push and re-checking what changed.')).toBeTruthy();
});

it('uses theme colors by default and keeps white text for the dark tone', () => {
  const { rerender } = render(<DefenseSwitch project={project} />);
  expect(screen.getByTestId('defense-switch').classList.contains('text-white')).toBe(false);

  rerender(<DefenseSwitch project={project} tone="dark" />);
  expect(screen.getByTestId('defense-switch').classList.contains('text-white')).toBe(true);
});

it('PATCHes the whole settings object with defense disabled', async () => {
  const requests: { url: string; init?: RequestInit }[] = [];
  const fetcher: typeof fetch = async (input, init) => {
    const url = String(input);
    requests.push({ url, init });
    if (url.endsWith('/me')) return Response.json(session);
    const body = JSON.parse(init?.body as string) as { settings: ProjectSettings };
    return Response.json({ ...project, settings: body.settings });
  };
  const client = new ApiClient({ baseUrl: 'http://localhost/api/v1', fetch: fetcher });
  setApiClient(client);
  await client.session();

  render(<DefenseSwitch project={project} />);
  fireEvent.click(screen.getByRole('switch', { name: '24/7 defense' }));

  await waitFor(() => expect(requests.some(request => request.init?.method === 'PATCH')).toBe(true));
  const patch = requests.find(request => request.init?.method === 'PATCH');
  expect(patch?.url).toBe('http://localhost/api/v1/projects/prj_12345678');
  const body = JSON.parse(patch?.init?.body as string) as { name: string; settings: ProjectSettings };
  expect(body.name).toBe(project.name);
  expect(body.settings).toEqual({
    ...settings,
    monitoring_policy: { ...settings.monitoring_policy, enabled: false },
  });
  expect(screen.getByRole('switch', { name: '24/7 defense' }).getAttribute('aria-checked')).toBe('false');
});

it('reverts to On and shows the owner-only error when the PATCH is forbidden', async () => {
  const requests: { url: string; init?: RequestInit }[] = [];
  const fetcher: typeof fetch = async (input, init) => {
    const url = String(input);
    requests.push({ url, init });
    if (url.endsWith('/me')) return Response.json(session);
    return Response.json({
      error: { code: 'FORBIDDEN', message: 'Only project owners can update settings', details: {}, request_id: null },
    }, { status: 403 });
  };
  const client = new ApiClient({ baseUrl: 'http://localhost/api/v1', fetch: fetcher });
  setApiClient(client);
  await client.session();

  render(<DefenseSwitch project={project} />);
  fireEvent.click(screen.getByRole('switch', { name: '24/7 defense' }));

  await waitFor(() => expect(screen.getByTestId('error-state').textContent).toContain('Could not change 24/7 defense (only project owners can)'));
  const toggle = screen.getByRole('switch', { name: '24/7 defense' });
  expect(toggle.getAttribute('aria-checked')).toBe('true');
  expect(toggle.textContent).toContain('On');
});
