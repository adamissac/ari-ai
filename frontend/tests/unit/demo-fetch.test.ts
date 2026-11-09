import { ApiClient, watchAssessment } from '@hackatl/frontend-transport';
import { afterEach, describe, expect, it, vi } from 'vitest';
import fixtures from '@/lib/demo/console/fixtures.json';
import { api, setApiClient } from '@/lib/api';
import { demoFetch } from '@/lib/demo/console/fetch';
import { HIDDEN_IDS } from '@/lib/demo/console/sim';

const responses = fixtures.responses as Record<string, { status: number; body: unknown }>;
const projectId = fixtures.project_id;
const repoId = fixtures.repo_id;
const baseUrl = 'http://demo.test/api/v1';

function client() {
  return new ApiClient({ baseUrl, fetch: demoFetch });
}

afterEach(() => {
  setApiClient(undefined);
  document.cookie = 'ari_demo_view=; Max-Age=0; Path=/';
  vi.unstubAllGlobals();
});

describe('demoFetch', () => {
  it('routes recorded requests and replays the captured artifact 404', async () => {
    const apiClient = client();
    expect((await apiClient.project(projectId)).name).toBe('Lumen Pay');
    const missingArtifact = Object.entries(responses).find(([key, value]) =>
      key.startsWith('GET /artifacts/') && value.status === 404,
    );
    expect(missingArtifact).toBeDefined();
    const [key, fixture] = missingArtifact!;
    const response = await demoFetch(`${baseUrl}${key.slice('GET '.length)}`);
    expect(response.status).toBe(404);
    expect(await response.json()).toEqual(fixture.body);
  });

  it('returns the standard 404 for unknown GETs', async () => {
    const response = await demoFetch(`${baseUrl}/not-in-demo`);
    expect(response.status).toBe(404);
    expect(await response.json()).toEqual({
      error: { code: 'NOT_FOUND', message: 'Not part of the demo account', details: {}, request_id: null },
    });
  });

  it('blocks mutations and permits a local logout response', async () => {
    const mutation = await demoFetch(`${baseUrl}/projects/${projectId}/incidents`, { method: 'POST' });
    expect(mutation.status).toBe(403);
    expect(await mutation.json()).toEqual({
      error: { code: 'FORBIDDEN', message: 'This is the demo account: actions are turned off.', details: {}, request_id: null },
    });
    expect((await demoFetch(`${baseUrl}/auth/logout`, { method: 'POST' })).status).toBe(204);
  });

  it('shifts timestamps relative to the fixture capture time', async () => {
    const original = (responses['GET /me']!.body as { user: { created_at: string } }).user.created_at;
    const before = Date.now();
    const me = await (await demoFetch(`${baseUrl}/me`)).json() as { user: { created_at: string } };
    const after = Date.now();
    const expected = Date.parse(original) + before - Date.parse(fixtures.captured_at);
    expect(Math.abs(Date.parse(me.user.created_at) - expected)).toBeLessThan(100);
    expect(Date.parse(me.user.created_at)).toBeGreaterThan(Date.parse(original));
    expect(after).toBeGreaterThanOrEqual(before);
  });

  it('decodes every JSON fixture through its matching ApiClient method', async () => {
    const apiClient = client();
    for (const [key, fixture] of Object.entries(responses)) {
      const route = key.slice('GET '.length);
      const url = new URL(route, baseUrl);
      const segments = url.pathname.split('/').filter(Boolean);
      let read: (() => Promise<unknown>) | undefined;
      if (url.pathname === '/me') read = () => apiClient.session();
      else if (url.pathname === '/projects') read = () => apiClient.projects();
      else if (segments[0] === 'projects' && segments.length === 2) read = () => apiClient.project(segments[1]!);
      else if (segments[0] === 'projects' && segments[2] === 'repositories') read = () => apiClient.repositories(segments[1]!);
      else if (segments[0] === 'projects' && segments[2] === 'scopes') read = () => apiClient.scopes(segments[1]!);
      else if (segments[0] === 'projects' && segments[2] === 'delivery-authority') read = () => apiClient.deliveryAuthority(segments[1]!);
      else if (segments[0] === 'projects' && segments[2] === 'assessments') read = () => apiClient.assessments(segments[1]!, url.searchParams.has('repo_id') ? { repoId: url.searchParams.get('repo_id')! } : {});
      else if (segments[0] === 'projects' && segments[2] === 'findings') read = () => apiClient.findings(segments[1]!, url.searchParams.has('repo_id') ? { repoId: url.searchParams.get('repo_id')! } : {});
      else if (segments[0] === 'projects' && segments[2] === 'approvals') {
        read = () => url.searchParams.get('status') === 'pending'
          ? apiClient.pendingApprovals(segments[1]!)
          : apiClient.approvals(segments[1]!, url.searchParams.has('repo_id') ? { repoId: url.searchParams.get('repo_id')! } : {});
      } else if (segments[0] === 'repositories' && segments.length === 2) read = () => apiClient.repository(segments[1]!);
      else if (segments[0] === 'repositories' && segments[2] === 'setup') read = () => apiClient.repositorySetup(segments[1]!);
      else if (segments[0] === 'repositories' && segments[2] === 'automation-status') read = () => apiClient.automationStatus(segments[1]!);
      else if (segments[0] === 'repositories' && segments[2] === 'commits') read = () => apiClient.repositoryCommits(segments[1]!);
      else if (segments[0] === 'repositories' && segments[2] === 'snapshots') read = () => apiClient.snapshots(segments[1]!, { limit: Number(url.searchParams.get('limit') ?? 100) });
      else if (segments[0] === 'snapshots' && segments.length === 2) read = () => apiClient.snapshot(segments[1]!);
      else if (segments[0] === 'assessments' && segments.length === 2) read = () => apiClient.assessment(segments[1]!);
      else if (segments[0] === 'assessments' && segments[2] === 'runs') read = () => apiClient.agentRuns(segments[1]!);
      else if (segments[0] === 'assessments' && segments[2] === 'events' && segments[3] === 'log') read = () => apiClient.eventsLog(segments[1]!, Number(url.searchParams.get('after') ?? 0));
      else if (segments[0] === 'assessments' && segments[2] === 'report') read = () => apiClient.report(segments[1]!);
      else if (segments[0] === 'findings' && segments.length === 2) read = () => apiClient.finding(segments[1]!);
      else if (segments[0] === 'findings' && segments[2] === 'patches') read = () => apiClient.patches(segments[1]!);
      else if (segments[0] === 'artifacts' && segments.length === 2) read = () => apiClient.artifactText(segments[1]!);
      else if (segments[0] === 'assessments' && segments[2] === 'events') {
        const response = await apiClient.fetch(`${baseUrl}${url.pathname}${url.search}`, { headers: { Accept: 'text/event-stream' } });
        expect(response.status).toBe([...HIDDEN_IDS].some(id => key.includes(id)) ? 404 : fixture.status);
        if (response.status === 200) expect(response.headers.get('content-type')).toMatch(/^text\/event-stream/);
        continue;
      }
      expect(read, `No ApiClient decoder for ${key}`).toBeDefined();
      // The paused recording is replaced by the account's seeded replay and is never served.
      if ([...HIDDEN_IDS].some(id => key.includes(id))) await expect(read!()).rejects.toMatchObject({ status: 404 });
      else if (fixture.status === 200) await expect(read!()).resolves.toBeDefined();
      else await expect(read!()).rejects.toMatchObject({ status: fixture.status });
    }
  });

  it('parses the captured completed assessment SSE stream', async () => {
    const assessmentPage = responses[`GET /projects/${projectId}/assessments?repo_id=${repoId}`]?.body as { items?: Array<{ id: string; state: string }> };
    const assessmentId = assessmentPage.items?.find(item => item.state === 'COMPLETED')?.id;
    expect(assessmentId).toBeDefined();
    const events = [];
    for await (const event of watchAssessment(client(), assessmentId!, { maxReconnects: 0 })) events.push(event);
    expect(events.length).toBeGreaterThan(0);
  });

  it('api() uses demoFetch only with the readable demo cookie', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation(async () => Response.json(responses['GET /me']!.body)));
    setApiClient(undefined);
    await api().session();
    expect(globalThis.fetch).toHaveBeenCalledOnce();

    vi.mocked(globalThis.fetch).mockClear();
    document.cookie = 'ari_demo_view=1; Path=/';
    expect((await api().session()).user.github_login).toBe('akshar-koth');
    expect(globalThis.fetch).not.toHaveBeenCalled();

    document.cookie = 'ari_demo_view=; Max-Age=0; Path=/';
    setApiClient(undefined);
    await api().session();
    expect(globalThis.fetch).toHaveBeenCalledOnce();
  });
});
