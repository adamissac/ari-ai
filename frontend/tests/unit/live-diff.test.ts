import { expect, it } from 'vitest';
import { countLines, MAX_LINES_PER_FILE, parsePatch } from '@/lib/live-diff';

it('parses a GitHub patch into hunks with line kinds', () => {
  const file = parsePatch({ filename: 'app.py', status: 'modified', additions: 1, deletions: 1, patch: '@@ -1,3 +1,3 @@\n def f():\n-    return 1\n+    return 2\n\\ No newline at end of file' });
  expect(file.path).toBe('app.py');
  expect(file.hunks).toHaveLength(1);
  expect(file.hunks[0]!.lines.map(l => l.kind)).toEqual([' ', '-', '+']);
  expect(file.hunks[0]!.lines[2]!.text).toBe('    return 2');
});

it('marks binary files and caps very long patches', () => {
  expect(parsePatch({ filename: 'logo.png', status: 'added', additions: 0, deletions: 0 }).hunks[0]!.lines[0]!.text).toContain('binary');
  const long = parsePatch({ filename: 'big.txt', status: 'added', additions: 500, deletions: 0, patch: `@@ -0,0 +1,500 @@\n${Array.from({ length: 500 }, (_, i) => `+line ${i}`).join('\n')}` });
  const lines = long.hunks[0]!.lines;
  expect(lines).toHaveLength(MAX_LINES_PER_FILE + 1);
  expect(lines.at(-1)!.text).toContain('100 more lines');
});

it('counts added and removed lines', () => {
  expect(countLines([{ kind: '+', text: 'a' }, { kind: '-', text: 'b' }, { kind: '+', text: 'c' }, { kind: ' ', text: 'd' }])).toEqual({ additions: 2, deletions: 1 });
});
