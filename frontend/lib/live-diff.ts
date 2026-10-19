import type { DiffFile, DiffLine, LineKind } from '@/lib/demo/scenarios';

/** Lines kept per file for display; the rest is summarised in one marker line. */
export const MAX_LINES_PER_FILE = 400;

/** One file of a GitHub commit, as returned by GET /repos/{owner}/{repo}/commits/{sha}. */
export interface GitHubFile { filename: string; status: string; additions: number; deletions: number; patch?: string }

/** Parse GitHub's per-file unified patch (hunks only, no file headers) into display hunks. */
export function parsePatch(file: GitHubFile): DiffFile {
  const hunks: DiffFile['hunks'] = [];
  let kept = 0;
  let dropped = 0;
  for (const raw of (file.patch ?? '').split('\n')) {
    if (raw.startsWith('@@')) {
      hunks.push({ header: raw, lines: [] });
      continue;
    }
    const hunk = hunks[hunks.length - 1];
    if (!hunk || raw.startsWith('\\')) continue; // "\ No newline at end of file"
    const kind: LineKind = raw[0] === '+' ? '+' : raw[0] === '-' ? '-' : ' ';
    if (kept >= MAX_LINES_PER_FILE) { dropped++; continue; }
    hunk.lines.push({ kind, text: raw.slice(1) });
    kept++;
  }
  const last = hunks[hunks.length - 1];
  if (dropped && last) last.lines.push({ kind: ' ', text: `… ${dropped} more line${dropped === 1 ? '' : 's'} not shown` });
  if (hunks.length === 0) {
    const why = file.patch === undefined ? 'binary or too large for GitHub to show a diff' : 'no line changes';
    hunks.push({ header: `@@ ${file.status} @@`, lines: [{ kind: ' ', text: `(${why})` }] });
  }
  return { path: file.filename, additions: file.additions, deletions: file.deletions, hunks };
}

/** Count +/- lines of a model-written patch so the header numbers match what is shown. */
export function countLines(lines: DiffLine[]): { additions: number; deletions: number } {
  return { additions: lines.filter(l => l.kind === '+').length, deletions: lines.filter(l => l.kind === '-').length };
}
