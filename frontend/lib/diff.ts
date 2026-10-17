export type DiffLine =
  | { kind: 'context' | 'add' | 'del'; text: string; oldNo: number | null; newNo: number | null }
  | { kind: 'hunk'; text: string; oldNo: null; newNo: null };
export interface DiffFile { oldPath: string; newPath: string; lines: DiffLine[]; added: number; removed: number }

const HUNK = /^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@/;
const strip = (p: string): string => p.replace(/^[ab]\//, '').replace(/\t.*$/, '');

/** Parse a unified diff into files with line numbers. Rendered as text only, never HTML. */
export function parseUnifiedDiff(diff: string): DiffFile[] {
  const files: DiffFile[] = [];
  let file: DiffFile | undefined;
  let oldNo = 0;
  let newNo = 0;
  for (const raw of diff.replace(/\r\n/g, '\n').split('\n')) {
    if (raw.startsWith('diff --git ')) { file = undefined; continue; }
    if (raw.startsWith('--- ')) {
      file = { oldPath: strip(raw.slice(4)), newPath: '', lines: [], added: 0, removed: 0 };
      files.push(file);
      continue;
    }
    if (raw.startsWith('+++ ') && file && !file.newPath) { file.newPath = strip(raw.slice(4)); continue; }
    if (!file) continue;
    const hunk = HUNK.exec(raw);
    if (hunk) {
      oldNo = Number(hunk[1]);
      newNo = Number(hunk[2]);
      file.lines.push({ kind: 'hunk', text: raw, oldNo: null, newNo: null });
    } else if (raw.startsWith('+')) {
      file.lines.push({ kind: 'add', text: raw.slice(1), oldNo: null, newNo: newNo++ });
      file.added++;
    } else if (raw.startsWith('-')) {
      file.lines.push({ kind: 'del', text: raw.slice(1), oldNo: oldNo++, newNo: null });
      file.removed++;
    } else if (raw.startsWith(' ')) {
      file.lines.push({ kind: 'context', text: raw.slice(1), oldNo: oldNo++, newNo: newNo++ });
    }
  }
  return files.filter(f => f.lines.length > 0);
}
