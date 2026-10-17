import { parseUnifiedDiff } from '@/lib/diff';

/** Line-numbered unified diff, rendered as text nodes only. */
export function DiffView({ diff }: { diff: string }) {
  const files = parseUnifiedDiff(diff);
  if (files.length === 0) return <pre className="mt-1 overflow-auto rounded bg-bg p-2 font-mono text-xs text-muted">{diff || '(empty diff)'}</pre>;
  return (
    <div className="mt-1 flex flex-col gap-2" data-testid="diff-view">
      {files.map((f, i) => (
        <figure key={i} className="overflow-hidden rounded border border-line">
          <figcaption className="flex justify-between bg-panel-2 px-2 py-1 font-mono text-xs">
            <span>{f.newPath === '/dev/null' ? f.oldPath : f.newPath}</span>
            <span><span className="text-ok">+{f.added}</span> <span className="text-bad">−{f.removed}</span></span>
          </figcaption>
          <div className="overflow-x-auto">
            <table className="w-full font-mono text-[0.75rem]">
              <tbody>
                {f.lines.map((l, j) => (
                  <tr key={j} className={l.kind === 'add' ? 'bg-ok/10' : l.kind === 'del' ? 'bg-bad/10' : l.kind === 'hunk' ? 'bg-indigo/10 text-faint' : ''}>
                    <td className="w-10 select-none pr-1 text-right text-faint">{l.oldNo ?? ''}</td>
                    <td className="w-10 select-none pr-1 text-right text-faint">{l.newNo ?? ''}</td>
                    <td className="w-4 select-none text-center text-faint" aria-hidden="true">{l.kind === 'add' ? '+' : l.kind === 'del' ? '−' : ''}</td>
                    <td className="whitespace-pre pr-2">
                      <span className="sr-only">{l.kind === 'add' ? 'added: ' : l.kind === 'del' ? 'removed: ' : ''}</span>{l.text}
                    </td>
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
