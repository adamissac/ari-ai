import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { expect, it } from 'vitest';

it('preserves the owner-supplied ant PNG byte-for-byte', () => {
  const source = readFileSync('public/brand/ari-ant.png');
  expect(createHash('sha256').update(source).digest('hex')).toBe('0d4d68e2e5917248016e2368773ac9a40417188737da6623485ecd82da47eeae');
  expect(source.readUInt32BE(16)).toBe(1254);
  expect(source.readUInt32BE(20)).toBe(1254);
  expect(readFileSync('app/icon.png')).toEqual(source);
});
