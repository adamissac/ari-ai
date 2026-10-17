import { describe, expect, it } from 'vitest';
import { analyze } from '@/lib/demo/scenarios';
import { simulatedAttack } from '@/lib/simulated-attack';

describe('simulatedAttack', () => {
  it('is deterministic per repository and names the real repository', () => {
    const a = simulatedAttack('acme/shop', 'trunk');
    expect(simulatedAttack('acme/shop', 'trunk')).toEqual(a);
    expect(a.repo.org).toBe('acme');
    expect(a.repo.name).toBe('shop');
    expect(a.commit.branch).toBe('trunk');
    expect(a.commit.message).toBe('Simulated attack on acme/shop');
  });

  it('always replays an attack the seven agents find and fix', () => {
    for (const name of ['acme/shop', 'acme/api', 'zeta/web', 'me/dotfiles', 'org/ml']) {
      const { repo, commit } = simulatedAttack(name, 'main');
      const analysis = analyze(repo, commit);
      expect(analysis.findings.length).toBeGreaterThan(0);
      expect(analysis.agents).toHaveLength(7);
    }
  });
});

describe('simulatedAttack with a real commit', () => {
  it('shows the real commit SHA, message and author', () => {
    const real = { sha: 'c'.repeat(40), message: 'feat: real change', author: 'alice' };
    const { commit } = simulatedAttack('acme/shop', 'main', real);
    expect(commit.sha).toBe(real.sha);
    expect(commit.message).toBe('feat: real change');
    expect(commit.author).toBe('alice');
  });
});
