import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import { ApiClient } from '@hackatl/frontend-transport';
import { LabSimulation } from '@/components/lab-simulation';
import { OptionalSession } from '@/components/session';
import { setApiClient } from '@/lib/api';
// Real output of rl_defense.lab_episode (first three steps), as the backend route returns it.
import fixtures from '../../transport/tests/fixtures/lab-simulation.json';

const me = { user: { id: 'usr_12345678', github_login: 'test', display_name: null, created_at: '2026-10-17T03:00:00Z' }, memberships: [], csrf_token: 'test-csrf' };
const status = {
  available: true, unavailable_reason: null, label: 'Simulated episode in DefenseSimEnv.', env_id: 'DefenseSimEnv-v0',
  scenarios: [{ name: 'eval_aggressive_noisy', split: 'eval', horizon: 200 }, { name: 'train_balanced', split: 'train', horizon: 200 }],
  policies: ['ddqn_trained', 'ddqn_untrained', 'random', 'noop', 'threshold_rules'],
  checkpoint: { sha256: fixtures.ddqn_trained.episode.policy.checkpoint_sha256, policy_version: fixtures.ddqn_trained.episode.policy.policy_version, path: 'rl-defense/results/protocol-v1-retrain/checkpoints/ddqn_seed0.pt' },
};
const unavailable = { available: false, unavailable_reason: 'the simulation engine is not installed in this API process (rl_defense)', label: 'x', scenarios: [], policies: [], checkpoint: null };
const error503 = { error: { code: 'SUBSYSTEM_UNAVAILABLE', message: 'Lab simulation unavailable: the lab checkpoint does not match its pinned sha256', details: {}, request_id: null } };

type Handler = (body: { scenario: string; policy: keyof typeof fixtures; episode_seed: number }) => Response;
function mount(options: { signedIn?: boolean; status?: unknown; episode?: Handler } = {}) {
  const calls: { url: string; body: unknown }[] = [];
  const fetch: typeof globalThis.fetch = async (input, init) => {
    const url = String(input);
    const body = init?.body ? JSON.parse(String(init.body)) : undefined;
    calls.push({ url, body });
    if (url.endsWith('/me')) return options.signedIn === false ? Response.json({ error: { code: 'UNAUTHENTICATED', message: 'sign in required', details: {}, request_id: null } }, { status: 401 }) : Response.json(me);
    if (url.endsWith('/lab/simulation')) return Response.json(options.status ?? status);
    if (url.endsWith('/lab/simulation/episodes')) return (options.episode ?? (b => Response.json(fixtures[b.policy])))(body);
    return Response.json({ error: { code: 'NOT_FOUND', message: 'not found', details: {}, request_id: null } }, { status: 404 });
  };
  setApiClient(new ApiClient({ baseUrl: 'http://localhost/api/v1', fetch }));
  render(<OptionalSession><LabSimulation /></OptionalSession>);
  return calls;
}
const episodeCalls = (calls: { url: string; body: unknown }[]) => calls.filter(c => c.url.endsWith('/episodes'));
/** The fixture is the engine's episode for seed 1003, so that is the seed the tests ask for. */
async function ready(): Promise<HTMLButtonElement> {
  const run = await screen.findByTestId('sim-run') as HTMLButtonElement;
  fireEvent.change(screen.getByLabelText('Episode seed'), { target: { value: '1003' } });
  return run;
}

afterEach(() => {
  cleanup();
  setApiClient(undefined);
});

it('asks a signed-out visitor to sign in and never calls the simulation API', async () => {
  const calls = mount({ signedIn: false });
  expect(screen.getByTestId('sim-signed-out').textContent).toContain('Sign in to run a simulation');
  await waitFor(() => expect(calls.some(c => c.url.endsWith('/me'))).toBe(true));
  expect(calls.some(c => c.url.includes('/lab/simulation'))).toBe(false);
  expect(screen.queryByTestId('sim-run')).toBeNull();
});

it('says why the engine is unavailable and offers nothing to run', async () => {
  const calls = mount({ status: unavailable });
  const notice = await screen.findByTestId('sim-unavailable');
  expect(notice.textContent).toContain('not installed in this API process');
  expect(notice.textContent).toContain('no substitute data is shown');
  expect(screen.queryByTestId('sim-run')).toBeNull();
  expect(episodeCalls(calls)).toHaveLength(0);
});

it('runs the requested episode on the backend and shows the first decision as returned', async () => {
  const calls = mount();
  fireEvent.click(await ready());
  await screen.findByTestId('sim-episode');
  fireEvent.click(screen.getByTestId('sim-pause'));
  fireEvent.click(screen.getByTestId('sim-reset'));

  expect(episodeCalls(calls)).toEqual([{ url: 'http://localhost/api/v1/lab/simulation/episodes', body: { scenario: 'eval_aggressive_noisy', policy: 'ddqn_trained', episode_seed: 1003 } }]);
  const { episode } = fixtures.ddqn_trained;
  const first = episode.steps[0]!;
  expect(screen.getByTestId('sim-policy').textContent).toContain('Learned checkpoint');
  expect(screen.getByTestId('sim-provenance').textContent).toContain(episode.policy.checkpoint_sha256!.slice(0, 12));
  expect(screen.getByTestId('sim-provenance').textContent).toContain(`${episode.policy.gradient_updates.toLocaleString()} gradient updates`);
  expect(screen.getByTestId('sim-progress').textContent).toContain('Step 1 of 3');
  expect(screen.getByTestId('sim-action').textContent).toBe(first.action_label);
  expect(screen.getByTestId('sim-mask').textContent).toContain(`${first.action_mask.filter(Boolean).length} of 22 actions`);
  expect(screen.getByTestId('sim-return').textContent).toBe(first.reward.toFixed(2));
  // the highest-scored allowed action leads the list, with the backend's Q-value
  const best = Math.max(...first.q_values!.filter((_, a) => first.action_mask[a]));
  expect(screen.getByTestId('sim-q').querySelector('li')!.textContent).toContain(best.toFixed(3));
  expect(screen.getByTestId('sim-observation').textContent).toContain('48 values');
  expect(screen.getByTestId('sim-truth').textContent).toContain('gateway');
});

it('steps, resets and plays through the episode it was given', async () => {
  mount();
  fireEvent.click(await ready());
  await screen.findByTestId('sim-episode');
  fireEvent.click(screen.getByTestId('sim-pause'));
  fireEvent.click(screen.getByTestId('sim-reset'));
  const { steps } = fixtures.ddqn_trained.episode;

  fireEvent.click(screen.getByTestId('sim-step'));
  expect(screen.getByTestId('sim-progress').textContent).toContain('Step 2 of 3');
  expect(screen.getByTestId('sim-action').textContent).toBe(steps[1]!.action_label);
  expect(screen.getByTestId('sim-return').textContent).toBe((steps[0]!.reward + steps[1]!.reward).toFixed(2));
  expect(screen.queryByTestId('sim-summary')).toBeNull();

  fireEvent.click(screen.getByTestId('sim-reset'));
  expect(screen.getByTestId('sim-progress').textContent).toContain('Step 1 of 3');

  fireEvent.click(screen.getByTestId('sim-play'));
  await waitFor(() => expect(screen.getByTestId('sim-progress').textContent).toContain('Step 3 of 3'), { timeout: 3000 });
  expect(screen.getByTestId('sim-summary').textContent).toContain(`Total return ${fixtures.ddqn_trained.episode.summary.total_return.toFixed(2)}`);
  expect((screen.getByTestId('sim-step') as HTMLButtonElement).disabled).toBe(true);

  fireEvent.click(screen.getByTestId('sim-stop'));
  expect(screen.queryByTestId('sim-episode')).toBeNull();
});

it('labels an untrained network and a scripted baseline as what they are', async () => {
  mount();
  await ready();
  fireEvent.change(screen.getByLabelText('Simulation policy'), { target: { value: 'ddqn_untrained' } });
  fireEvent.click(screen.getByTestId('sim-run'));
  await waitFor(() => expect(screen.getByTestId('sim-policy').textContent).toContain('Untrained network'));
  expect(screen.getByTestId('sim-provenance').textContent).toContain('0 gradient updates');
  expect(screen.getByTestId('sim-provenance').textContent).not.toContain('Checkpoint');

  fireEvent.change(screen.getByLabelText('Simulation policy'), { target: { value: 'threshold_rules' } });
  fireEvent.click(screen.getByTestId('sim-run'));
  await waitFor(() => expect(screen.getByTestId('sim-policy').textContent).toContain('Scripted baseline'));
  expect(screen.getByTestId('sim-no-q').textContent).toContain('no Q-values');
  expect(screen.queryByTestId('sim-q')).toBeNull();
});

it('shows a backend failure as a failure and keeps no episode on screen', async () => {
  let fail = false;
  mount({ episode: body => (fail ? Response.json(error503, { status: 503 }) : Response.json(fixtures[body.policy])) });
  fireEvent.click(await ready());
  await screen.findByTestId('sim-episode');
  fail = true;
  fireEvent.click(screen.getByTestId('sim-run'));
  const alert = await screen.findByTestId('error-state');
  expect(alert.textContent).toContain('The simulation did not run');
  expect(alert.textContent).toContain('SUBSYSTEM_UNAVAILABLE');
  expect(screen.queryByTestId('sim-episode')).toBeNull();
});

it('rejects a response that is not the episode it asked for', async () => {
  mount({ episode: () => Response.json(fixtures.threshold_rules) });
  fireEvent.click(await ready());
  expect((await screen.findByTestId('error-state')).textContent).toContain('episode does not match the request');
  expect(screen.queryByTestId('sim-episode')).toBeNull();
});

it('refuses a seed that is not a whole number in range before calling the backend', async () => {
  const calls = mount();
  const run = await screen.findByTestId('sim-run') as HTMLButtonElement;
  for (const bad of ['-1', '1.5', 'abc', '2147483648', '']) {
    fireEvent.change(screen.getByLabelText('Episode seed'), { target: { value: bad } });
    expect(run.disabled).toBe(true);
  }
  fireEvent.change(screen.getByLabelText('Episode seed'), { target: { value: '1003' } });
  expect(run.disabled).toBe(false);
  fireEvent.click(run);
  await waitFor(() => expect(episodeCalls(calls)).toHaveLength(1));
  expect(episodeCalls(calls)[0]!.body).toEqual({ scenario: 'eval_aggressive_noisy', policy: 'ddqn_trained', episode_seed: 1003 });
});

it('compares every policy on the same episode and ranks them by the returned totals', async () => {
  const policies = ['ddqn_trained', 'ddqn_untrained', 'threshold_rules'];
  const calls = mount({ status: { ...status, policies } });
  await ready();
  fireEvent.click(screen.getByTestId('sim-compare'));
  const table = await screen.findByTestId('sim-comparison');
  expect(episodeCalls(calls).map(c => (c.body as { policy: string; episode_seed: number }))).toEqual(policies.map(policy => ({ scenario: 'eval_aggressive_noisy', policy, episode_seed: 1003 })));
  const expected = policies
    .map(p => fixtures[p as keyof typeof fixtures].episode)
    .sort((a, b) => b.summary.total_return - a.summary.total_return);
  const rows = [...table.querySelectorAll('tbody tr')];
  expect(rows.map(r => r.getAttribute('data-testid'))).toEqual(expected.map(e => `sim-compare-${e.policy.kind}`));
  rows.forEach((row, i) => expect(row.textContent).toContain(expected[i]!.summary.total_return.toFixed(2)));
  expect(screen.getByTestId('sim-compare-ddqn_untrained').textContent).toContain('Untrained network');
  expect(table.textContent).toContain('not average performance');
});

it('shows no comparison table when any policy run fails', async () => {
  mount({ episode: body => (body.policy === 'ddqn_untrained' ? Response.json(error503, { status: 503 }) : Response.json(fixtures[body.policy])) });
  await ready();
  fireEvent.click(screen.getByTestId('sim-compare'));
  expect((await screen.findByTestId('error-state')).textContent).toContain('no table is shown');
  expect(screen.queryByTestId('sim-comparison')).toBeNull();
});

it('offers the deterministic rules the backend lists and sends the chosen one', async () => {
  const calls = mount({
    status: { ...status, policies: [...status.policies, 'exposed_guard', 'monitor_isolate'] },
    episode: () => Response.json(error503, { status: 503 }),
  });
  const run = await ready();
  const select = screen.getByLabelText('Simulation policy') as HTMLSelectElement;
  const labels = Array.from(select.options).map(o => o.textContent);
  expect(labels).toContain('Rule: rate-limit exposed nodes, isolate on anomaly');
  expect(labels).toContain('Rule: monitor exposed nodes, isolate on anomaly');
  fireEvent.change(select, { target: { value: 'monitor_isolate' } });
  fireEvent.click(run);
  await waitFor(() => expect(episodeCalls(calls)).toHaveLength(1));
  expect(episodeCalls(calls)[0]?.body).toMatchObject({ policy: 'monitor_isolate', episode_seed: 1003 });
  expect(screen.queryByTestId('sim-episode')).toBeNull();
});
