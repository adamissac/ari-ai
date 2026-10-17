import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { expect, it } from 'vitest';

it('preserves the owner-supplied ant PNG byte-for-byte', () => {
  const source = readFileSync('public/brand/ari-ant.png');
  expect(createHash('sha256').update(source).digest('hex')).toBe('0d4d68e2e5917248016e2368773ac9a40417188737da6623485ecd82da47eeae');
  expect(source.readUInt32BE(16)).toBe(1254);
  expect(source.readUInt32BE(20)).toBe(1254);
  // Buffer.equals is an exact native byte comparison; toEqual walks every byte and can time out.
  expect(readFileSync('app/icon.png').equals(source)).toBe(true);
});

it('ships a transparent, tightly cropped ant mark derived from the original', () => {
  const mark = readFileSync('public/brand/ari-ant-mark.png');
  expect(mark.subarray(1, 4).toString()).toBe('PNG');
  expect(mark.readUInt32BE(16)).toBe(361);
  expect(mark.readUInt32BE(20)).toBe(256);
  expect(mark[25]).toBe(6); // colour type 6 = RGBA (has transparency)
});
