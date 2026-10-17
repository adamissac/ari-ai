import { describe, expect, it } from 'vitest';
import { REQUEST_SCOPE_NOTE } from '@/lib/scope';

describe('request scope note', () => {
  it('names pending authorization and does not claim activation, a check, or open access', () => {
    expect(REQUEST_SCOPE_NOTE).toContain('pending authorization');
    expect(REQUEST_SCOPE_NOTE).toContain('different project member approves');
    expect(REQUEST_SCOPE_NOTE).toContain('does not start a check');
    expect(REQUEST_SCOPE_NOTE).toContain('outside those targets');
  });
});
