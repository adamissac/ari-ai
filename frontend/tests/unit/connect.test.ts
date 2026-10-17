import { describe, expect, it } from 'vitest';
import { CONNECT_REPOSITORY_NOTE } from '@/lib/connect';

describe('connect repository note', () => {
  it('does not claim the form installs GitHub, approves a scope, or starts a check', () => {
    expect(CONNECT_REPOSITORY_NOTE).toContain('does not attach a GitHub App installation');
    expect(CONNECT_REPOSITORY_NOTE).toContain('approve a test environment');
    expect(CONNECT_REPOSITORY_NOTE).toContain('start a check');
  });
});
