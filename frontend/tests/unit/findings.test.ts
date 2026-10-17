import { describe, expect, it } from 'vitest';
import { findingGroup } from '@/lib/findings';

describe('finding groups', () => {
  it('does not call an inconclusive or rejected fix validated', () => {
    expect(findingGroup('hypothesis')).toBe('hypothesis');
    expect(findingGroup('inconclusive')).toBe('open');
    expect(findingGroup('patch_rejected')).toBe('open');
    expect(findingGroup('validated')).toBe('open');
    expect(findingGroup('verified')).toBe('fixed');
    expect(findingGroup('hardened')).toBe('fixed');
    expect(findingGroup('refuted')).toBe('closed');
    expect(findingGroup('accepted_risk')).toBe('closed');
    expect(findingGroup('closed')).toBe('closed');
  });
});
