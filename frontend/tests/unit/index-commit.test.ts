import { describe, expect, it } from 'vitest';
import { INDEX_COMMIT_NOTE } from '@/lib/index-commit';

describe('index commit note', () => {
  it('does not claim a security check or a repository change', () => {
    expect(INDEX_COMMIT_NOTE).toContain('symbols, calls, entry points, and expectations');
    expect(INDEX_COMMIT_NOTE).toContain('does not run a security check');
    expect(INDEX_COMMIT_NOTE).toContain('change the repository');
  });
});
