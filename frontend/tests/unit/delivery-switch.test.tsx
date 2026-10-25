import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { ApiClient, type MeResponse, type Project, type ProjectSettings } from '@hackatl/frontend-transport';
import { DeliverySwitch } from '@/components/delivery-switch';
import { setApiClient } from '@/lib/api';

const settings: ProjectSettings = {
  default_budget: { max_tokens: 400_000, max_usd: 10, max_wall_clock_s: 1800 },
  monitoring_policy: {
    enabled: true,
    min_interval_s: 600,
    ignore_paths_only: ['tests/**'],
    monitoring_budget: { max_tokens: 150_000, max_usd: 3, max_wall_clock_s: 900 },
  },
  languages: ['python'],
  delivery_mode: 'pull_request',
  delivery_authorized_by: null,
};
const project: Project = { id: 'prj_12345678', org_id: 'org_12345678', name: 'Payments', settings, created_at: '2026-10-23T00:00:00Z' };
const session: MeResponse = {
  user: { id: 'usr_12345678', github_login: 'tester', display_name: null, created_at: '2026-10-23T00:00:00Z' },
  memberships: [],
  csrf_token: 'test-csrf',
};

afterEach(() => {
  cleanup();
  setApiClient(undefined);
  vi.restoreAllMocks();
});

async function installClient(current: Project) {
  const requests: { url: string; init?: RequestInit }[] = [];
  const fetcher: typeof fetch = async (input, init) => {
    const url = String(input);
    requests.push({ url, init });
    if (url.endsWith('/me')) return Response.json(session);
    const body = JSON.parse(init?.body as string) as { settings: ProjectSettings };
    return Response.json({
      ...current,
      settings: { ...body.settings, delivery_authorized_by: 'usr_12345678' },
    });
  };
  const client = new ApiClient({ baseUrl: 'http://localhost/api/v1', fetch: fetcher });
  setApiClient(client);
  await client.session();
  return requests;
}

it('shows PR when fixes arrive as pull requests', () => {
  render(<DeliverySwitch project={project} />);
  const toggle = screen.getByRole('switch', { name: 'Auto-open fix PRs' });
  expect(toggle.getAttribute('aria-checked')).toBe('true');
  expect(toggle.textContent).toContain('PR');
});

it('switches manual delivery to pull requests without an auto-commit confirmation', async () => {
  const manualProject: Project = {
    ...project,
    settings: { ...settings, delivery_mode: 'manual' },
  };
  const requests = await installClient(manualProject);
  const confirm = vi.spyOn(window, 'confirm');
  render(<DeliverySwitch project={manualProject} />);
  fireEvent.click(screen.getByRole('switch', { name: 'Auto-open fix PRs' }));
  expect(confirm).not.toHaveBeenCalled();

  await waitFor(() => expect(screen.getByRole('switch', { name: 'Auto-open fix PRs' }).getAttribute('aria-checked')).toBe('true'));
  const patch = requests.find(request => request.init?.method === 'PATCH');
  const body = JSON.parse(patch?.init?.body as string) as { settings: ProjectSettings };
  expect(body.settings).toEqual({ ...manualProject.settings, delivery_mode: 'pull_request' });
});

it('switches pull-request delivery off to manual', async () => {
  const requests = await installClient(project);
  const confirm = vi.spyOn(window, 'confirm');
  render(<DeliverySwitch project={project} />);
  fireEvent.click(screen.getByRole('switch', { name: 'Auto-open fix PRs' }));
  expect(confirm).not.toHaveBeenCalled();

  await waitFor(() => expect(screen.getByRole('switch', { name: 'Auto-open fix PRs' }).getAttribute('aria-checked')).toBe('false'));
  const patch = requests.find(request => request.init?.method === 'PATCH');
  const body = JSON.parse(patch?.init?.body as string) as { settings: ProjectSettings };
  expect(body.settings).toEqual({ ...settings, delivery_mode: 'manual' });
});

it('never selects auto-commit from the 7 Agents switch', async () => {
  const autoProject: Project = {
    ...project,
    settings: { ...settings, delivery_mode: 'auto' },
  };
  const requests = await installClient(autoProject);
  render(<DeliverySwitch project={autoProject} />);
  const toggle = screen.getByRole('switch', { name: 'Auto-open fix PRs' });
  expect(toggle.getAttribute('aria-checked')).toBe('false');
  expect(toggle.textContent).toContain('Settings');
  fireEvent.click(toggle);

  await waitFor(() => expect(toggle.getAttribute('aria-checked')).toBe('true'));
  const patch = requests.find(request => request.init?.method === 'PATCH');
  const body = JSON.parse(patch?.init?.body as string) as { settings: ProjectSettings };
  expect(body.settings.delivery_mode).toBe('pull_request');
});
