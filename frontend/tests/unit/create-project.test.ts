import { describe, expect, it } from 'vitest';
import { CREATE_PROJECT_NOTE } from '@/lib/create-project';

describe('create project note', () => {
  it('does not claim a repository, a scope, or a check, and does not hide the monitoring default', () => {
    expect(CREATE_PROJECT_NOTE).toContain('does not connect a repository');
    expect(CREATE_PROJECT_NOTE).toContain('approve a test environment');
    expect(CREATE_PROJECT_NOTE).toContain('start a check');
    expect(CREATE_PROJECT_NOTE).toContain('Monitoring is on by default');
    expect(CREATE_PROJECT_NOTE).toContain('events that actually arrive');
  });
});
