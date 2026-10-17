import type { DiffFile } from '@/lib/diff';

/** Plain-language before/after of one fix, from recorded validation and verification. */
export interface Side { headline: string; tone: 'bad' | 'ok' | 'warn' | 'neutral'; detail: string }
export interface CheckLine { label: string; passed: boolean }

export const CHECK_PLAIN: Record<string, string> = {
  original_check_now_fails_to_reproduce: 'The original problem no longer happens',
  functional_suite_passes: 'The normal tests still pass',
  generated_tests_pass: 'New tests written for this problem pass',
  no_test_tampering: 'No existing test was weakened to make it pass',
  diff_scope_ok: 'The fix changed only the files that were planned',
};

/** Statuses reached only after a test confirmed the problem. Inconclusive, closed, accepted-risk and stale are not proof of a failing test. */
const CONFIRMED_STATUSES: ReadonlySet<string> = new Set(['validated', 'diagnosed', 'patch_proposed', 'verified', 'patch_rejected', 'unresolved', 'hardened']);

export function beforeSide(input: { kind: string; status: string; validation: 'confirmed' | 'refuted' | 'inconclusive' | null }): Side {
  if (input.validation === 'confirmed') return { headline: 'The problem was reproduced', tone: 'bad', detail: 'An approved test in a sealed-off copy made the problem happen.' };
  if (input.validation === 'refuted') return { headline: 'The problem did not reproduce', tone: 'ok', detail: 'An approved test could not make the suspected problem happen.' };
  if (input.validation === 'inconclusive') return { headline: 'The test was inconclusive', tone: 'warn', detail: 'An approved test ran but could not decide either way.' };
  if (input.kind === 'functional' && input.status === 'refuted') {
    return { headline: 'The problem did not reproduce', tone: 'ok', detail: 'The reviewer could not reproduce this suspected behaviour problem.' };
  }
  if (input.kind === 'functional' && CONFIRMED_STATUSES.has(input.status)) {
    return { headline: 'A test showed the wrong behaviour', tone: 'bad', detail: 'The reviewer recorded executed-test evidence for this behaviour problem (listed under the finding evidence).' };
  }
  return { headline: 'No reproduction recorded', tone: 'neutral', detail: 'No test result before the fix is recorded for this finding.' };
}

export function afterSide(verification: { verdict: 'accepted' | 'rejected'; checks: readonly { name: string; passed: boolean }[] } | null, hasPatch: boolean): { side: Side; checks: CheckLine[] } {
  if (!hasPatch) return { side: { headline: 'No fix proposed', tone: 'neutral', detail: 'No candidate fix is recorded for this finding.' }, checks: [] };
  if (!verification) return { side: { headline: 'Fix not yet verified', tone: 'warn', detail: 'A fix was proposed, but independent re-testing has not recorded a verdict. It does not count as a fix yet.' }, checks: [] };
  const checks = verification.checks.map(c => ({ label: CHECK_PLAIN[c.name] ?? c.name, passed: c.passed }));
  const passed = checks.filter(c => c.passed).length;
  return verification.verdict === 'accepted'
    ? { side: { headline: 'Independent re-test accepted the fix', tone: 'ok', detail: `${passed} of ${checks.length} checks passed. The fix lives in an isolated copy; it was not merged or deployed.` }, checks }
    : { side: { headline: 'Independent re-test rejected the fix', tone: 'bad', detail: `${passed} of ${checks.length} checks passed. A rejected patch is not a fix.` }, checks };
}

export type SplitCell = { no: number; text: string; kind: 'context' | 'del' | 'add' } | null;
export interface SplitRow { left: SplitCell; right: SplitCell; hunk?: string }

/** Pair removed and added lines side by side; unchanged lines appear on both sides. */
export function splitRows(file: DiffFile): SplitRow[] {
  const rows: SplitRow[] = [];
  let dels: SplitCell[] = [];
  let adds: SplitCell[] = [];
  const flush = () => {
    for (let i = 0; i < Math.max(dels.length, adds.length); i++) rows.push({ left: dels[i] ?? null, right: adds[i] ?? null });
    dels = [];
    adds = [];
  };
  for (const line of file.lines) {
    if (line.kind === 'hunk') { flush(); rows.push({ left: null, right: null, hunk: line.text }); }
    else if (line.kind === 'del') dels.push({ no: line.oldNo ?? 0, text: line.text, kind: 'del' });
    else if (line.kind === 'add') adds.push({ no: line.newNo ?? 0, text: line.text, kind: 'add' });
    else { flush(); rows.push({ left: { no: line.oldNo ?? 0, text: line.text, kind: 'context' }, right: { no: line.newNo ?? 0, text: line.text, kind: 'context' } }); }
  }
  flush();
  return rows;
}
