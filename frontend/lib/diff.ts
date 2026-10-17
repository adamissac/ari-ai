export type DiffLine =
  | { kind: 'context' | 'add' | 'del'; text: string; oldNo: number | null; newNo: number | null }
  | { kind: 'hunk'; text: string; oldNo: null; newNo: null };
export interface DiffFile { oldPath: string; newPath: string; lines: DiffLine[]; added: number; removed: number }

const HUNK = /^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@/;
const strip = (p: string): string => p.replace(/^[ab]\//, '').replace(/\t.*$/, '');

/** Parse a unified diff into files with line numbers. Rendered as text only, never HTML. */
export function parseUnifiedDiff(diff: string): DiffFile[] {
  const files: DiffFile[] = [];
  let file: DiffFile | undefined;
  let oldNo = 0;
  let newNo = 0;
  // Lines still owed to the current hunk, from its header counts. Inside a hunk every line is
  // content (a removed line "-- x" is not a header); ---/+++ only mean a header outside one.
  let oldLeft = 0;
  let newLeft = 0;
  for (const raw of diff.replace(/\r\n/g, '\n').split('\n')) {
    if (file && (oldLeft > 0 || newLeft > 0)) {
      if (raw.startsWith('\\')) continue; // "\ No newline at end of file"
      if (raw.startsWith('+') && newLeft > 0) {
        file.lines.push({ kind: 'add', text: raw.slice(1), oldNo: null, newNo: newNo++ });
        file.added++;
        newLeft--;
        continue;
      }
      if (raw.startsWith('-') && oldLeft > 0) {
        file.lines.push({ kind: 'del', text: raw.slice(1), oldNo: oldNo++, newNo: null });
        file.removed++;
        oldLeft--;
        continue;
      }
      if ((raw.startsWith(' ') || raw === '') && oldLeft > 0 && newLeft > 0) {
        // An empty line is a context line whose single leading space was trimmed.
        file.lines.push({ kind: 'context', text: raw.slice(1), oldNo: oldNo++, newNo: newNo++ });
        oldLeft--;
        newLeft--;
        continue;
      }
      oldLeft = 0; // the hunk ended early or its counts are wrong; read this line as a header
      newLeft = 0;
    }
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
      oldLeft = hunk[2] === undefined ? 1 : Number(hunk[2]);
      newNo = Number(hunk[3]);
      newLeft = hunk[4] === undefined ? 1 : Number(hunk[4]);
      file.lines.push({ kind: 'hunk', text: raw, oldNo: null, newNo: null });
    }
  }
  return files.filter(f => f.lines.length > 0);
}
