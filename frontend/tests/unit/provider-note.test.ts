import { describe, expect, it } from 'vitest';
import { providerNote } from '@/lib/relay';

describe('provider note', () => {
  it('is empty when every turn was live', () => {
    expect(providerNote([['live', 3]])).toBe('');
    expect(providerNote([])).toBe('');
  });
  it('calls only fake and replay turns scripted or replayed', () => {
    const note = providerNote([['fake', 9], ['none', 1]]);
    expect(note).toContain('9 scripted');
    expect(note).toContain('1 with no model call');
    expect(providerNote([['replay', 2]])).toContain('2 replayed from a recording');
  });
  it('deterministic-only runs are never described as scripted model replies', () => {
    expect(providerNote([['none', 4]])).not.toMatch(/scripted/);
  });
  it('counts live turns as live in a mixed run', () => {
    expect(providerNote([['live', 2], ['fake', 1]])).toContain('2 from a live model, 1 scripted');
  });
  it('names an unrecognised mode instead of guessing', () => {
    expect(providerNote([['weird', 1]])).toContain('unrecognised provider mode (weird)');
  });
});
