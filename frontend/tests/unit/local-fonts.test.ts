import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { expect, it } from 'vitest';

const root = resolve(import.meta.dirname, '../..');
it('builds typography from local assets instead of external font services', () => {
  const layout = readFileSync(resolve(root, 'app/layout.tsx'), 'utf8');
  expect(layout).not.toContain('next/font/google');
  expect(layout).toContain("from 'next/font/local'");
});
it('ships intact WOFF2 fonts with their redistribution licenses', () => {
  const sources = JSON.parse(readFileSync(resolve(root, 'app/fonts/SOURCES.json'), 'utf8')) as {
    packages: { license: string; files: { path: string; sha256: string }[] }[];
  };
  expect(sources.packages).toHaveLength(3);
  for (const pkg of sources.packages) {
    expect(readFileSync(resolve(root, 'app/fonts', pkg.license), 'utf8')).toMatch(/SIL OPEN FONT LICENSE|SIL Open Font License/);
    for (const file of pkg.files) {
      const data = readFileSync(resolve(root, 'app/fonts', file.path));
      expect(data.subarray(0, 4).toString()).toBe('wOF2');
      expect(createHash('sha256').update(data).digest('hex')).toBe(file.sha256);
    }
  }
});
