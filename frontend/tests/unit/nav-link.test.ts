import { describe, expect, it } from 'vitest';
import { isCurrentSection } from '@/components/nav-link';

describe('header tab highlight', () => {
  it('marks a section current on its page and pages beneath it', () => {
    expect(isCurrentSection('/projects', '/projects')).toBe(true);
    expect(isCurrentSection('/projects/prj_1/assessments/asm_1', '/projects')).toBe(true);
    expect(isCurrentSection('/lab', '/lab')).toBe(true);
    expect(isCurrentSection('/pricing', '/pricing')).toBe(true);
  });
  it('does not match other sections or lookalike prefixes', () => {
    expect(isCurrentSection('/', '/projects')).toBe(false);
    expect(isCurrentSection('/labs', '/lab')).toBe(false);
    expect(isCurrentSection('/projectsx', '/projects')).toBe(false);
    expect(isCurrentSection('/lab', '/pricing')).toBe(false);
  });
});
