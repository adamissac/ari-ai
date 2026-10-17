import { describe, expect, it } from 'vitest';
import { parseUnifiedDiff } from '@/lib/diff';

describe('unified diff parser: hunk-aware', () => {
  it('a removed line that looks like a file header ("--- x") stays a removed line', () => {
    const diff = '--- a/q.sql\n+++ b/q.sql\n@@ -1,3 +1,2 @@\n keep\n--- old comment\n tail\n';
    const files = parseUnifiedDiff(diff);
    expect(files).toHaveLength(1);
    const lines = files[0]?.lines ?? [];
    expect(lines.map(l => l.kind)).toEqual(['hunk', 'context', 'del', 'context']);
    expect(lines[2]).toMatchObject({ kind: 'del', text: '-- old comment', oldNo: 2 });
    expect(files[0]?.removed).toBe(1);
  });

  it('an added line that looks like a file header ("+++ x") stays an added line', () => {
    const diff = '--- a/n.txt\n+++ b/n.txt\n@@ -1,1 +1,2 @@\n a\n+++ plus plus\n';
    const files = parseUnifiedDiff(diff);
    expect(files).toHaveLength(1);
    expect(files[0]?.lines[2]).toMatchObject({ kind: 'add', text: '++ plus plus', newNo: 2 });
    expect(files[0]?.newPath).toBe('n.txt');
  });

  it('an empty line inside a hunk is empty context and advances both line numbers', () => {
    const diff = '--- a/f.py\n+++ b/f.py\n@@ -1,4 +1,4 @@\n a\n\n-b\n+B\n c\n';
    const lines = parseUnifiedDiff(diff)[0]?.lines ?? [];
    expect(lines[2]).toMatchObject({ kind: 'context', text: '', oldNo: 2, newNo: 2 });
    expect(lines[3]).toMatchObject({ kind: 'del', oldNo: 3 });
    expect(lines[4]).toMatchObject({ kind: 'add', newNo: 3 });
    expect(lines[5]).toMatchObject({ kind: 'context', oldNo: 4, newNo: 4 });
  });

  it('the trailing newline after the last hunk line is not a line, and a second file still starts', () => {
    const diff = 'diff --git a/a b/a\n--- a/a\n+++ b/a\n@@ -1 +1 @@\n-x\n+y\ndiff --git a/b b/b\n--- a/b\n+++ b/b\n@@ -0,0 +1,2 @@\n+one\n+two\n';
    const files = parseUnifiedDiff(diff);
    expect(files.map(f => f.newPath)).toEqual(['a', 'b']);
    expect(files[0]).toMatchObject({ added: 1, removed: 1 });
    expect(files[1]?.lines.map(l => l.kind)).toEqual(['hunk', 'add', 'add']);
    expect(files[1]?.lines[2]).toMatchObject({ newNo: 2 });
  });

  it('ignores the "No newline at end of file" marker', () => {
    const diff = '--- a/a\n+++ b/a\n@@ -1 +1 @@\n-x\n\\ No newline at end of file\n+y\n';
    const lines = parseUnifiedDiff(diff)[0]?.lines ?? [];
    expect(lines.map(l => l.kind)).toEqual(['hunk', 'del', 'add']);
  });
});
