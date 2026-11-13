import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { ApiClient, ApiError, ProtocolError } from '../dist/frontend/transport/src/index.js';

// Real output of rl_defense.lab_episode.run_lab_episode (eval_aggressive_noisy, seed 1003,
// first 3 steps), wrapped as the backend route returns it. Not hand-written.
const fixtures = JSON.parse(readFileSync(new URL('./fixtures/lab-simulation.json', import.meta.url), 'utf8'));
const json = (body, status = 200) => Response.json(body, { status });
const me = { user: { id: 'usr_12345678', github_login: 'test', display_name: null, created_at: '2026-10-17T03:00:00Z' }, memberships: [], csrf_token: 'test-csrf' };
const request = (policy = 'ddqn_trained') => ({ scenario: 'eval_aggressive_noisy', policy, episode_seed: 1003 });
const copy = (policy = 'ddqn_trained') => structuredClone(fixtures[policy]);
async function signedIn(handler) {
  const calls = [];
  const api = new ApiClient({ baseUrl: 'http://localhost/api/v1', fetch: async (url, init) => { calls.push({ url: String(url), init }); return String(url).endsWith('/me') ? json(me) : handler(String(url), init); } });
  await api.session();
  return { api, calls };
}
const status = {
  available: true, unavailable_reason: null, label: 'Simulated episode', env_id: 'DefenseSimEnv-v0',
  scenarios: [{ name: 'eval_aggressive_noisy', split: 'eval', horizon: 200 }],
  policies: ['ddqn_trained', 'ddqn_untrained', 'random', 'noop', 'threshold_rules'],
  checkpoint: { sha256: 'a'.repeat(64), policy_version: 'DefenseSimEnv-v0@aaaaaaaaaaaa', path: 'rl-defense/results/x.pt' },
};

test('a real engine episode decodes for learned, untrained and scripted policies', async () => {
  for (const policy of ['ddqn_trained', 'ddqn_untrained', 'threshold_rules']) {
    const { api, calls } = await signedIn(() => json(copy(policy)));
    const { episode, label } = await api.runLabSimulation(request(policy));
    assert.match(label, /no action is executed/);
    assert.equal(episode.kind, 'simulation');
    assert.equal(episode.steps.length, 3);
    assert.equal(episode.steps[0].observation.length, episode.feature_names.length);
    assert.equal(episode.steps[0].q_values === null, policy === 'threshold_rules');
    const sent = calls.at(-1);
    assert.ok(sent.url.endsWith('/lab/simulation/episodes'));
    assert.equal(sent.init.method, 'POST');
    assert.equal(sent.init.headers.get('X-CSRF-Token'), 'test-csrf');
    assert.deepEqual(JSON.parse(sent.init.body), request(policy));
  }
  const trained = copy().episode.policy;
  assert.equal(trained.source, 'learned_checkpoint');
  assert.ok(trained.gradient_updates > 0 && /^[0-9a-f]{64}$/.test(trained.checkpoint_sha256));
  assert.equal(copy('ddqn_untrained').episode.policy.gradient_updates, 0);
});

test('an internally inconsistent episode is rejected, not drawn', async () => {
  const mutations = {
    'not labelled a simulation': b => { b.episode.kind = 'live'; },
    'masked action taken': b => { const s = b.episode.steps[0]; s.action_mask[s.action] = false; },
    'reward is not the sum of its components': b => { b.episode.steps[1].reward += 5; b.episode.summary.total_return += 5; },
    'return is not the sum of rewards': b => { b.episode.summary.total_return += 1; },
    'NaN-like reward': b => { b.episode.steps[0].reward = null; },
    'observation out of range': b => { b.episode.steps[0].observation[0] = 1.5; },
    'observation of the wrong length': b => { b.episode.steps[0].observation.pop(); },
    'Q-values missing for a learned policy': b => { b.episode.steps[0].q_values = null; },
    'baseline dressed up as learned': b => { b.episode.policy.source = 'scripted_baseline'; },
    'learned policy without a checkpoint': b => { b.episode.policy.checkpoint_sha256 = null; },
    'learned policy with zero updates': b => { b.episode.policy.gradient_updates = 0; },
    'wrong action label': b => { b.episode.steps[0].action_label = 'isolate:db'; },
    'steps out of order': b => { b.episode.steps[1].t = 5; },
    'answer for another seed': b => { b.episode.episode_seed = 7; },
    'answer for another scenario': b => { b.episode.scenario.name = 'train_balanced'; },
    'missing reward component': b => { delete b.episode.steps[0].reward_components.impact; },
  };
  for (const [name, mutate] of Object.entries(mutations)) {
    const body = copy();
    mutate(body);
    const { api } = await signedIn(() => json(body));
    await assert.rejects(api.runLabSimulation(request()), ProtocolError, name);
  }
  const untrained = copy('ddqn_untrained');
  untrained.episode.policy.gradient_updates = 10;
  const { api } = await signedIn(() => json(untrained));
  await assert.rejects(api.runLabSimulation(request('ddqn_untrained')), ProtocolError);
});

test('a backend failure is an ApiError, never an episode', async () => {
  const { api } = await signedIn(() => json({ error: { code: 'SUBSYSTEM_UNAVAILABLE', message: 'Lab simulation unavailable: the simulation engine is not installed', details: {}, request_id: null } }, 503));
  await assert.rejects(api.runLabSimulation(request()), e => e instanceof ApiError && e.status === 503 && e.error.code === 'SUBSYSTEM_UNAVAILABLE');
});

test('invalid requests never reach the network and a mutation needs a session', async () => {
  let called = 0;
  const { api } = await signedIn(() => { called += 1; return json(copy()); });
  for (const bad of [{ ...request(), policy: 'ppo' }, { ...request(), episode_seed: -1 }, { ...request(), episode_seed: 1.5 }, { ...request(), scenario: '../x' }]) {
    await assert.rejects(api.runLabSimulation(bad), ProtocolError);
  }
  assert.equal(called, 0);
  const anonymous = new ApiClient({ baseUrl: 'http://localhost/api/v1', fetch: async () => json(copy()) });
  await assert.rejects(anonymous.runLabSimulation(request()), ProtocolError);
});

test('status is consistent: available with a checkpoint, or unavailable with a reason', async () => {
  const { api } = await signedIn(() => json(status));
  const ok = await api.labSimulationStatus();
  assert.equal(ok.available, true);
  assert.equal(ok.scenarios[0].name, 'eval_aggressive_noisy');
  const down = { available: false, unavailable_reason: 'the simulation engine is not installed', label: 'x', scenarios: [], policies: [], checkpoint: null };
  assert.equal((await (await signedIn(() => json(down))).api.labSimulationStatus()).unavailable_reason, down.unavailable_reason);
  for (const body of [
    { ...status, checkpoint: null },
    { ...status, unavailable_reason: 'but also broken' },
    { ...down, unavailable_reason: null },
    { ...down, scenarios: status.scenarios },
    { ...status, policies: ['ppo'] },
    { ...status, checkpoint: { ...status.checkpoint, sha256: 'short' } },
  ]) {
    await assert.rejects((await signedIn(() => json(body))).api.labSimulationStatus(), ProtocolError);
  }
});
