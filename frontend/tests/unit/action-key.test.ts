import { describe, expect, it } from 'vitest';
import { ActionKeys } from '@/lib/action-key';

describe('ActionKeys', () => {
  const make = () => { let n = 0; return new ActionKeys('t', p => `${p}-${++n}`); };
  it('reuses the key while the same action is retried', () => {
    const keys = make();
    expect(keys.keyFor('create|a')).toBe('t-1');
    expect(keys.keyFor('create|a')).toBe('t-1');
  });
  it('changing the inputs is a new action with a new key', () => {
    const keys = make();
    keys.keyFor('create|a');
    expect(keys.keyFor('create|b')).toBe('t-2');
  });
  it('a retried action resends the exact body built the first time', () => {
    const keys = make();
    let n = 0;
    const first = keys.payloadFor('scope|a', () => ({ expires: ++n }));
    expect(keys.payloadFor('scope|a', () => ({ expires: ++n }))).toBe(first);
    expect(keys.payloadFor('scope|b', () => ({ expires: ++n }))).toEqual({ expires: 2 });
  });
  it('after success the same inputs are a new action', () => {
    const keys = make();
    keys.keyFor('create|a');
    keys.done();
    expect(keys.keyFor('create|a')).toBe('t-2');
  });
});
