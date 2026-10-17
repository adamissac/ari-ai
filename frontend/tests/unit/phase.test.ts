import { describe, expect, it } from 'vitest';
import { currentPhaseSentence } from '@/lib/phase';

describe('assessment phase sentence', () => {
  it('does not treat a finished check as a secure application', () => {
    expect(currentPhaseSentence('COMPLETED')).toMatch(/not a claim that the whole application is secure/);
  });
  it('names the recorded state and keeps approval from sounding like a merge', () => {
    expect(currentPhaseSentence('VALIDATION')).toBe('This check is in Validation.');
    expect(currentPhaseSentence('AWAITING_APPROVAL')).toMatch(/Nothing is merged or deployed/);
    expect(currentPhaseSentence('FAILED')).toMatch(/not a clean result/);
  });
});
