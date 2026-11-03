import { ApiClient, ApiError, watchAssessment, type StreamEvent } from '@hackatl/frontend-transport';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import fixtures from '@/lib/demo/console/fixtures.json';
import { demoFetch } from '@/lib/demo/console/fetch';
import { demoQuickRead } from '@/lib/demo/console/quick-read';
import { REPLAY_PACE_MS } from '@/lib/demo/console/sim';
import { DEMO_GITHUB_REPOS, resetDemoSimulation } from '@/lib/demo/console/state';

const projectId = fixtures.project_id;
const recordedSha = (fixtures.responses[`GET /assessments/asm_01M6FV2SMWPFS8PH97GT8X4FB2`].body as { assessment: { commit_sha: string } }).assessment.commit_sha;
const repoId = fixtures.repo_id;
async function client() {
  const api = new ApiClient({ baseUrl: 'http://demo.test/api/v1', fetch: demoFetch });
  await api.session();
  return api;
}

beforeEach(() => {
  resetDemoSimulation();
  vi.useFakeTimers({ now: Date.parse('2026-11-10T12:00:00Z'), toFake: ['Date'] });
});
afterEach(() => {
  vi.useRealTimers();
  resetDemoSimulation();
});

async function paused(api: ApiClient) {
  const list = await api.assessments(projectId);
  return list.items.find(a => a.state === 'AWAITING_APPROVAL')!;
}

describe('demo account simulation', () => {
  it('lists several fictional repositories, only payments-api connected, with no GitHub links', async () => {
    const api = await client();
    const repos = await api.githubRepositories();
    expect(repos.items.map(r => r.full_name)).toEqual(DEMO_GITHUB_REPOS.map(r => `lumen-pay/${r.name}`));
    expect(repos.items.length).toBeGreaterThanOrEqual(5);
    expect(repos.items.filter(r => r.connected_repo_id).map(r => r.full_name)).toEqual(['lumen-pay/payments-api']);
    expect(repos.install_url).toBeNull();
    const commits = await api.repositoryCommits(repoId);
    expect(commits.items.every(c => c.html_url === null)).toBe(true);
    expect((await api.projects()).items.map(p => p.name)).toEqual(['Lumen Pay']);
  });

  it('connects a repository and walks setup, scope approval and a first check, all in the browser', async () => {
    const api = await client();
    const repo = await api.connectRepository(projectId, { full_name: 'lumen-pay/checkout-web', default_branch: 'main', installation_id: 4242 });
    expect((await api.githubRepositories()).items.find(r => r.full_name === 'lumen-pay/checkout-web')!.connected_repo_id).toBe(repo.id);
    expect((await api.repositories(projectId)).items.map(r => r.id)).toContain(repo.id);

    const blank = await api.repositorySetup(repo.id);
    expect(blank.complete).toBe(false);
    const saved = await api.saveRepositorySetup(repo.id, { answers: { ...blank.answers, readiness: true }, complete: false });
    expect(saved.answers.readiness).toBe(true);
    expect((await api.repositorySetup(repo.id)).answers.readiness).toBe(true);

    const project = await api.project(projectId);
    await api.updateProject(projectId, { name: project.name, settings: { ...project.settings, delivery_mode: 'pull_request' } });
    expect((await api.project(projectId)).settings.delivery_mode).toBe('pull_request');
    expect((await api.deliveryAuthority(projectId)).configured_mode).toBe('pull_request');
    expect((await api.updateRepository(repo.id, { automatic_assessments: true })).automatic_assessments).toBe(true);

    await expect(api.startAssessment(projectId, { scope_id: 'scp_missing0', repo_id: repo.id, commit_sha: null, snapshot_id: null, budget: null }, 'k1'))
      .rejects.toMatchObject({ status: 403 });
    const scope = await api.createScope(projectId, {
      name: 'checkout-web sandbox', notes: null, expires_at: new Date(Date.now() + 30 * 86_400_000).toISOString(),
      targets: [{ kind: 'sandbox_build', repo_id: repo.id, exposed_ports: [], build_recipe_ref: 'build_recipe.json' }],
      allowed_check_categories: ['access_control.ownership'],
    }, { idempotencyKey: 'k2' });
    expect(scope.status).toBe('pending');
    expect((await api.approveScope(scope.id)).status).toBe('active');
    expect((await api.automationStatus(repo.id)).reasons.map(r => r.code)).toContain('project_monitoring_off');

    const started = await api.startAssessment(projectId, { scope_id: scope.id, repo_id: repo.id, commit_sha: null, snapshot_id: null, budget: null }, 'k3');
    expect(started.repo_id).toBe(repo.id);
    vi.setSystemTime(Date.now() + 60 * REPLAY_PACE_MS);
    const detail = await api.assessment(started.id);
    expect(detail.assessment.state).toBe('COMPLETED');
    expect(detail.findings).toEqual([]);
    expect(detail.agent_runs.map(r => r.agent).sort()).toEqual(['reviewer', 'scout']);
  });

  it('opens with a recorded check paused for approval that the visitor can approve and watch finish', async () => {
    const api = await client();
    const run = await paused(api);
    expect(run.repo_id).toBe(repoId);
    const pending = (await api.pendingApprovals(projectId)).items;
    expect(pending.length).toBe(2);
    const before = await api.assessment(run.id);
    expect(before.agent_runs.map(r => r.agent)).not.toContain('patch');

    for (const approval of pending) await api.decideApproval(approval.id, { decision: 'approved', reason: null }, { idempotencyKey: approval.id });
    expect((await api.pendingApprovals(projectId)).items).toEqual([]);
    // Resumes at the decision itself: the page stops polling while a demo check awaits approval.
    expect((await api.assessment(run.id)).assessment.state).toBe('REMEDIATION');

    vi.setSystemTime(Date.now() + 5 * REPLAY_PACE_MS);
    const midway = await api.assessment(run.id);
    expect(['REMEDIATION', 'HARDENING']).toContain(midway.assessment.state);
    expect(midway.agent_runs.some(r => r.status === 'running' || r.agent === 'patch')).toBe(true);

    vi.setSystemTime(Date.now() + 60 * REPLAY_PACE_MS);
    const done = await api.assessment(run.id);
    expect(done.assessment.state).toBe('COMPLETED');
    expect(done.agent_runs.map(r => r.agent)).toEqual(expect.arrayContaining(['scout', 'probe', 'trace', 'diagnose', 'patch', 'fortify', 'verify']));
    expect(done.findings.map(f => f.status).sort()).toEqual(['hardened', 'verified']);
    const finding = done.findings[0]!;
    expect((await api.finding(finding.id)).finding.id).toBe(finding.id);
    expect((await api.patches(done.findings.find(f => f.status === 'verified')!.id)).items.length).toBeGreaterThan(0);
    expect((await api.report(run.id)).assessment.id).toBe(run.id);

    const log = await api.eventsLog(run.id, 0);
    expect(log.items.at(-1)!.type).toBe('assessment.completed');
    const streamed: StreamEvent[] = [];
    for await (const event of watchAssessment(api, run.id)) streamed.push(event);
    expect(streamed.length).toBe(log.items.length);
  });

  it('keeps recorded history read-only', async () => {
    const api = await client();
    const recordedApproval = (await api.approvals(projectId)).items.find(a => !a.id.includes('-r'))!;
    await expect(api.decideApproval(recordedApproval.id, { decision: 'approved', reason: null }, { idempotencyKey: 'x' })).rejects.toBeInstanceOf(ApiError);
  });

  it('serves a sample quick read for listed and known commits without a network call', () => {
    const lookup = demoQuickRead('lumen-pay/payments-api', recordedSha, { message: 'feat(payments): add GET /payments/{payment_id} lookup', author: 'akshar-koth', committed_at: null });
    expect(lookup?.verdict).toBe('needs_review');
    expect(lookup?.commit.htmlUrl).toBe('');
    const checkout = DEMO_GITHUB_REPOS.find(r => r.name === 'checkout-web')!;
    expect(demoQuickRead('lumen-pay/checkout-web', checkout.commits[1]!.sha)?.verdict).toBe('clean');
  });
});
