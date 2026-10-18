import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ReplayStage } from '@/components/lab-replay';
import { actionMeaning, keyMoments, latestAction, nodeViews, overallStatus, serviceInfo, signalLevel, stepStory, storyMoments } from '@/lib/lab-story';
import type { LabEpisode, LabNodeState, LabScenario, LabStep } from '@/lib/lab-types';

const scenario: LabScenario = {
  name: 'eval_aggressive_noisy', config_hash: 'x', split: 'eval', horizon: 8,
  nodes: [
    { name: 'api', criticality: 0.5, exposed: true, finding_severity: 0.5 },
    { name: 'db', criticality: 1, exposed: false, finding_severity: 0.1 },
  ],
  edges: [['api', 'db']],
};
const node = (name: string, v: number, extra: Partial<LabNodeState> = {}): LabNodeState => ({
  node: name, alert_rate: v, anomaly_score: v, monitoring_level: 0, rate_limited: false, isolated: false, reassessment_pending: false, hidden_stage_ground_truth: 'none', ...extra,
});
const step = (t: number, action: string, api: number, db: number, ext: { api?: Partial<LabNodeState>; db?: Partial<LabNodeState> } = {}, reward = -0.1): LabStep => ({
  t, action, reward, reward_components: { action_cost: reward, disruption: 0, adversary_progress: 0 }, nodes: [node('api', api, ext.api), node('db', db, ext.db)],
});
// api turns suspicious at t=2; the AI cuts api off at t=3; api is isolated from t=4 and calms down.
const steps: LabStep[] = [
  step(0, 'noop', 0.1, 0.05),
  step(1, 'noop', 0.4, 0.05),
  step(2, 'raise_monitoring:api', 0.7, 0.05),
  step(3, 'isolate:api', 0.75, 0.05, { api: { monitoring_level: 1 } }),
  step(4, 'noop', 0.5, 0.05, { api: { isolated: true, monitoring_level: 1 } }),
  step(5, 'noop', 0.3, 0.05, { api: { isolated: true } }),
  step(6, 'noop', 0.2, 0.05, { api: { isolated: true } }),
  step(7, 'noop', 0.1, 0.05, { api: { isolated: true } }),
  step(8, 'noop', 0.1, 0.05),
];
const episode: LabEpisode = { policy: 'ddqn', scenario: scenario.name, episode_seed: 1, training_seed: 0, total_return: -1, compromised: false, impact_nodes: [], steps };

describe('lab story model', () => {
  it('names services in plain words', () => {
    expect(serviceInfo('payments').label).toBe('Payments');
    expect(serviceInfo('db').kind).toBe('database');
    expect(serviceInfo('mystery').label).toBe('mystery');
  });

  it('bands observed signals and never invents a verdict for missing data', () => {
    expect(signalLevel(node('x', 0.1))).toBe('quiet');
    expect(signalLevel(node('x', 0.4))).toBe('elevated');
    expect(signalLevel(node('x', 0.6))).toBe('high');
    expect(signalLevel(undefined)).toBe('unknown');
    expect(nodeViews(scenario, [])[0]!.signal).toBe('unknown');
  });

  it('explains actions in plain English, true to the simulator', () => {
    expect(actionMeaning('isolate:api', n => n.toUpperCase()).did).toContain('cut API off');
    expect(actionMeaning('isolate:api').tradeoff).toContain('unavailable');
    expect(actionMeaning('raise_monitoring:db').tradeoff).toBe('No disruption to users.');
    expect(actionMeaning('noop').did).toContain('no action');
  });

  it('finds key moments from recorded data only', () => {
    const m = keyMoments(episode, scenario);
    expect(m.map(x => `${x.t}:${x.kind}`)).toEqual(['2:signal', '2:action', '3:disruptive', '8:end']);
    expect(m.at(-1)!.text).toContain('never reached its goal');
    expect(storyMoments(m, 3).at(-1)!.kind).toBe('end');
  });

  it('story moments favour real beats over routine repeated moves', () => {
    const m = (t: number, kind: 'signal' | 'action' | 'disruptive' | 'end', node: string | null, text: string) => ({ t, kind, node, text });
    const many = [
      ...Array.from({ length: 10 }, (_, i) => m(i, 'action', 'api', 'AI: Watch closely API server')),
      m(20, 'signal', 'db', 'Suspicious activity at Database'),
      m(30, 'disruptive', 'db', 'AI: Cut off Database'),
      m(31, 'disruptive', 'db', 'AI: Cut off Database'),
      m(40, 'end', null, 'Game over'),
    ];
    const picked = storyMoments(many, 8).map(x => x.t);
    expect(picked).toEqual([0, 20, 30, 40]); // first watch, first suspicious signal, first cut-off, end
  });

  it('says what happened, what the AI did, and admits the reasoning is not recorded', () => {
    const s = stepStory(episode, scenario, 3);
    expect(s.now).toBe('Suspicious activity at API server (0.75).');
    expect(s.did).toContain('cut API server off');
    expect(s.why).toContain('does not include the policy’s reasoning');
    expect(s.why).toContain('strongest signal it could see (API server, 0.75)');
    expect(s.effect).toContain('API server is now cut off');
    expect(s.effect).toContain('five steps later its signal dropped (0.75 → 0.10)');
    expect(stepStory(episode, scenario, 0).now).toBe('Signals are quiet across all 2 services.');
  });

  it('summarizes the current status and the latest action', () => {
    expect(overallStatus(scenario, steps[3]).text).toBe('Suspicious activity at 1 service');
    expect(overallStatus(scenario, steps[0]).tone).toBe('quiet');
    expect(latestAction(episode, 6)).toEqual({ t: 3, action: 'isolate:api' });
    expect(latestAction(episode, 1)).toBeNull();
  });
});

describe('replay stage', () => {
  beforeEach(() => {
    vi.stubGlobal('requestAnimationFrame', vi.fn().mockReturnValue(1));
    vi.stubGlobal('cancelAnimationFrame', vi.fn());
  });
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

  it('labels the view as a recorded simulation and tells the step story', () => {
    render(<ReplayStage episode={episode} scenario={scenario} />);
    expect(screen.getByTestId('lab-mode').textContent).toBe('Isolated test network · recorded evaluation');
    expect(screen.getByTestId('lab-step-action').textContent).toContain('At step 0 the defender:');
    expect(screen.getByTestId('lab-step-story').textContent).toContain('quiet');
  });

  it('jumps between key moments and updates every view', () => {
    render(<ReplayStage episode={episode} scenario={scenario} />);
    fireEvent.click(screen.getByRole('button', { name: 'Next key moment' }));
    expect(screen.getByText('t = 2 / 8')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Next key moment' }));
    expect(screen.getByText('t = 3 / 8')).toBeTruthy();
    expect(screen.getByTestId('lab-step-action').textContent).toContain('cut API server off');
    expect(screen.getByTestId('lab-status').textContent).toContain('Suspicious activity at 1 service');
    expect(screen.getByRole('button', { name: /^API server \(api\)/ }).getAttribute('data-signal')).toBe('high');
  });

  it('replay shows labeled attacker truth and lets viewers hide it', () => {
    render(<ReplayStage episode={episode} scenario={scenario} />);
    fireEvent.change(screen.getByLabelText('Step', { selector: 'input' }), { target: { value: '4' } });
    fireEvent.keyDown(screen.getByRole('button', { name: /^API server/ }), { key: 'Enter' });
    const panel = screen.getByTestId('lab-service-panel');
    expect(panel.textContent).toContain('API server');
    expect(panel.textContent).toContain('cut off');
    expect(panel.textContent).toContain('AI actions here so far: 2');
    expect(panel.textContent).toContain('Hidden truth (not seen by the defender)');
    fireEvent.click(screen.getByLabelText('Show on the map (for learning)'));
    expect(screen.getByTestId('lab-service-panel').textContent).not.toContain('Hidden truth');
  });
});
