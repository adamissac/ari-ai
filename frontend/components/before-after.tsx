'use client';

import type { PatchView } from '@hackatl/frontend-transport';
import type { ReactNode } from 'react';
import { Term } from '@/components/term';
import { ErrorState, Loading, Mono } from '@/components/ui';
import { api } from '@/lib/api';
import { afterSide, beforeSide, splitRows, type Side } from '@/lib/before-after';
import { parseUnifiedDiff } from '@/lib/diff';
import { useResource } from '@/lib/use-resource';

const TONE: Record<Side['tone'], string> = {
  bad: 'border-bad/50 bg-bad/[0.05] text-bad',
  ok: 'border-ok/50 bg-ok/[0.05] text-ok',
  warn: 'border-warn/50 bg-warn/[0.06] text-warn',
  neutral: 'border-line bg-panel-2 text-muted',
};
const ICON: Record<Side['tone'], string> = { bad: '✗', ok: '✓', warn: '!', neutral: '·' };

/**
 * Before and after one fix: the recorded test result before (Probe / reviewer), the
 * independent re-test after (Verify), and the code on each side from the latest
 * patch's diff artifact (size-bounded, SHA-256 checked against the server header and
 * the patch record). Missing records are said plainly; nothing is inferred.
 */
export function BeforeAfter({ kind, status, validation, patches, patchesError }: {
  kind: string;
  status: string;
  validation: 'confirmed' | 'refuted' | 'inconclusive' | null;
  /** null while loading; [] only when the request succeeded with zero patches. */
  patches: PatchView[] | null;
  /** Set when the patch request failed; patches is ignored then. */
  patchesError?: { error: unknown; onRetry: () => void } | null;
}) {
  const failed = patchesError != null;
  const latest = failed ? null : patches?.[patches.length - 1] ?? null;
  const before = beforeSide({ kind, status, validation });
  const after = afterSide(latest?.verification ?? null, latest !== null);
  return (
    <section aria-labelledby="ba-title" className="rounded-xl border border-line bg-panel p-5" data-testid="before-after">
      <h2 id="ba-title" className="text-lg font-semibold tracking-tight">Before and after the fix</h2>
      <p className="mt-1 text-sm text-muted">
        Left: what the tests showed before. Right: what an independent <Term t="verification">re-test</Term> showed after the proposed <Term t="patch">fix</Term>.
      </p>
      <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
        <SideCard label="Before" side={before} testId="ba-before" />
        {failed ? (
          <div data-testid="ba-after"><ErrorState error={patchesError.error} onRetry={patchesError.onRetry} context="Patch record" /></div>
        ) : patches === null ? (
          <div data-testid="ba-after" className="rounded-lg border-2 border-line bg-panel-2 p-4"><Loading label="Loading the proposed fix" /></div>
        ) : <SideCard label="After" side={after.side} testId="ba-after">
          {after.checks.length > 0 && (
            <ul className="mt-2 flex flex-col gap-1 text-sm text-ink" aria-label="Re-test checks">
              {after.checks.map(c => (
                <li key={c.label} className="flex items-start gap-1.5">
                  <span aria-hidden="true" className={c.passed ? 'text-ok' : 'text-bad'}>{c.passed ? '✓' : '✗'}</span>
                  <span>{c.label}<span className="sr-only">: {c.passed ? 'passed' : 'failed'}</span></span>
                </li>
              ))}
            </ul>
          )}
        </SideCard>}
      </div>
      {!failed && patches === null ? null : latest && <CodeChange view={latest} />}
    </section>
  );
}

function SideCard({ label, side, testId, children }: { label: string; side: Side; testId: string; children?: ReactNode }) {
  return (
    <div className={`rounded-lg border-2 p-4 ${TONE[side.tone]}`} data-testid={testId}>
      <p className="label-mono">{label}</p>
      <p className="mt-1 flex items-center gap-2 text-base font-semibold"><span aria-hidden="true">{ICON[side.tone]}</span>{side.headline}</p>
      <p className="mt-1 text-sm text-ink/80">{side.detail}</p>
      {children}
    </div>
  );
}

function CodeChange({ view }: { view: PatchView }) {
  const diff = useResource(`ba-diff:${view.patch.diff_artifact_id}`, signal => api().artifactText(view.patch.diff_artifact_id, { signal }));
  if (diff.status === 'loading') return <Loading label="Loading the code change" />;
  if (diff.status === 'error') return <div className="mt-3"><ErrorState error={diff.error} onRetry={diff.reload} context="Code change" /></div>;
  const recordMatches = diff.data.sha256 === view.patch.diff_sha256;
  const files = parseUnifiedDiff(diff.data.text);
  return (
    <div className="mt-4" data-testid="ba-code">
      <p className="text-xs text-muted">
        The code change, side by side. Red lines were removed, green lines were added. Proposed in an isolated copy (<Mono>{view.patch.worktree_ref.split('/').pop()}</Mono>); not merged or deployed.
        {' '}<span data-testid="ba-hash">{recordMatches
          ? 'The diff matches the hash recorded with the patch.'
          : 'Warning: the diff does not match the hash recorded with the patch.'}</span>
      </p>
      {files.length === 0 ? <p className="mt-2 text-sm text-muted">The diff could not be read as a code change.</p> : files.map((f, i) => (
        <figure key={i} className="mt-2 overflow-hidden rounded-lg border border-line">
          <figcaption className="bg-panel-2 px-3 py-1.5 font-mono text-xs">{f.newPath === '/dev/null' ? f.oldPath : f.newPath} {f.oldPath === '/dev/null' && <span className="text-faint">(new file)</span>}</figcaption>
          <div className="overflow-x-auto">
            <table className="w-full table-fixed font-mono text-[0.75rem]">
              <thead className="text-left text-faint">
                <tr><th className="w-1/2 px-2 py-1 font-sans font-semibold">Before</th><th className="w-1/2 border-l border-line px-2 py-1 font-sans font-semibold">After</th></tr>
              </thead>
              <tbody>
                {splitRows(f).map((row, j) => row.hunk !== undefined ? (
                  <tr key={j} className="bg-panel-2 text-faint"><td colSpan={2} className="px-2 py-0.5">⋯</td></tr>
                ) : (
                  <tr key={j}>
                    <Cell cell={row.left} />
                    <Cell cell={row.right} border />
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </figure>
      ))}
    </div>
  );
}

function Cell({ cell, border = false }: { cell: ReturnType<typeof splitRows>[number]['left']; border?: boolean }) {
  const bg = cell?.kind === 'del' ? 'bg-bad/10' : cell?.kind === 'add' ? 'bg-ok/10' : '';
  return (
    <td className={`whitespace-pre-wrap break-all px-2 align-top ${bg} ${border ? 'border-l border-line' : ''}`}>
      {cell && <><span className="mr-2 select-none text-faint">{cell.no}</span><span className="sr-only">{cell.kind === 'del' ? 'removed: ' : cell.kind === 'add' ? 'added: ' : ''}</span>{cell.text}</>}
    </td>
  );
}
