import { describe, expect, it } from 'vitest';
import { chooseCandidate } from '@/components/incident-closure';

describe('chooseCandidate', () => {
  const list = [{ id: 'a' }, { id: 'b' }];
  it('returns the selected candidate', () => expect(chooseCandidate(list, 'b')).toEqual({ id: 'b' }));
  it('falls back to the first when the selection left the list', () => expect(chooseCandidate([{ id: 'a' }], 'b')).toEqual({ id: 'a' }));
  it('is undefined for an empty list', () => expect(chooseCandidate([], 'a')).toBeUndefined());
});
