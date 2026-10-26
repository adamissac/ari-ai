import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { ConsoleSide } from '@/components/lab-console';
import type { LabEpisode, LabScenario } from '@/lib/lab-types';

const scenario: LabScenario = {
  name: 'test', config_hash: 'hash', split: 'eval', horizon: 4,
  nodes: [{ name: 'payments', criticality: 0.8, exposed: true, finding_severity: 0.5 }],
  edges: [],
};

const episode: LabEpisode = {
  policy: 'ddqn', scenario: scenario.name, episode_seed: 1, training_seed: 1,
  total_return: 0, compromised: false, impact_nodes: [],
  steps: [
    { t: 0, action: 'noop', reward: 0, reward_components: {}, nodes: [] },
    { t: 1, action: 'noop', reward: 0, reward_components: {}, nodes: [] },
    { t: 3, action: 'isolate:payments', reward: 0, reward_components: {}, nodes: [] },
  ],
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it('queues disruptive recorded actions at their step and keeps approval local to the demo', () => {
  const fetch = vi.fn();
  vi.stubGlobal('fetch', fetch);
  const view = render(<ConsoleSide episode={episode} scenario={scenario} t={2} />);

  expect(screen.getByText('Nothing waiting.')).toBeTruthy();
  expect(screen.queryByRole('button', { name: 'Approve' })).toBeNull();

  view.rerender(<ConsoleSide episode={episode} scenario={scenario} t={3} />);
  expect(screen.getAllByText('Cut payments off from the network')).toHaveLength(2);
  fireEvent.click(screen.getByRole('button', { name: 'Approve' }));
  expect(screen.getByText('Approved · demo only, nothing was changed')).toBeTruthy();
  expect(fetch).not.toHaveBeenCalled();
});
