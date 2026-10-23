import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
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
  delivery_mode: 'review',
  auto_delivery_enabled_by: null,
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
});

it('shows Review by default', () => {
  render(<DeliverySwitch project={project} />);
  const toggle = screen.getByRole('switch', { name: 'Auto-commit fixes' });
  expect(toggle.getAttribute('aria-checked')).toBe('false');
  expect(toggle.textContent).toContain('Review');
});

it('PATCHes delivery_mode auto and keeps the rest of the settings', async () => {
  const requests: { url: string; init?: RequestInit }[] = [];
  const fetcher: typeof fetch = async (input, init) => {
    const url = String(input);
    requests.push({ url, init });
    if (url.endsWith('/me')) return Response.json(session);
    const body = JSON.parse(init?.body as string) as { settings: ProjectSettings };
    return Response.json({ ...project, settings: { ...body.settings, auto_delivery_enabled_by: 'usr_12345678' } });
  };
  const client = new ApiClient({ baseUrl: 'http://localhost/api/v1', fetch: fetcher });
  setApiClient(client);
  await client.session();

  render(<DeliverySwitch project={project} />);
  fireEvent.click(screen.getByRole('switch', { name: 'Auto-commit fixes' }));

  await waitFor(() => expect(screen.getByRole('switch', { name: 'Auto-commit fixes' }).getAttribute('aria-checked')).toBe('true'));
  const patch = requests.find(request => request.init?.method === 'PATCH');
  const body = JSON.parse(patch?.init?.body as string) as { settings: ProjectSettings };
  expect(body.settings).toEqual({ ...settings, delivery_mode: 'auto' });
});
