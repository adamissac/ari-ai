'use client';

import type { EvidenceRef } from '@hackatl/frontend-transport';
import { useState } from 'react';
import { DiffView } from '@/components/diff-view';
import { Button, ErrorState, Loading, Mono, Tag } from '@/components/ui';
import { api } from '@/lib/api';
import { githubLink, shortSha } from '@/lib/format';

/** One evidence reference: source span (linked at the exact SHA), artifact (fetched on demand) or note. */
export function Evidence({ item, repoFullName }: { item: EvidenceRef; repoFullName?: string | undefined }) {
  const href = item.kind === 'source_span' ? githubLink(repoFullName, item.commit_sha, item.path, item.span?.start_line, item.span?.end_line) : null;
  const where = item.path ? `${item.path}${item.span ? `:${item.span.start_line}${item.span.end_line !== item.span.start_line ? `-${item.span.end_line}` : ''}` : ''}` : null;
  return (
    <div className="rounded border border-line/70 bg-bg/60 px-2 py-1.5 text-xs">
      <p className="flex flex-wrap items-center gap-1.5">
        <Tag>{item.kind.replace('_', ' ')}</Tag>
        {where && (href ? <a className="font-mono text-accent hover:underline" href={href} target="_blank" rel="noreferrer">{where}</a> : <Mono>{where}</Mono>)}
        {item.commit_sha && <span className="text-faint">@ {shortSha(item.commit_sha)}</span>}
        {item.symbol && <Mono>{item.symbol}</Mono>}
        <span className="text-faint">via {item.provenance}</span>
      </p>
      {item.note && <p className="mt-1 text-muted">{item.note}</p>}
      {item.artifact_id && <ArtifactPeek id={item.artifact_id} />}
    </div>
  );
}

export function EvidenceList({ items, repoFullName }: { items: EvidenceRef[]; repoFullName?: string | undefined }) {
  if (items.length === 0) return <p className="text-xs text-faint">No evidence references.</p>;
  return <div className="flex flex-col gap-1.5">{items.map((e, i) => <Evidence key={i} item={e} repoFullName={repoFullName} />)}</div>;
}

/** Artifacts are fetched only when asked, size-bounded and hash-checked, rendered as text. */
export function ArtifactPeek({ id, label = 'artifact', asDiff = false }: { id: string; label?: string; asDiff?: boolean }) {
  const [state, setState] = useState<{ status: 'idle' } | { status: 'loading' } | { status: 'ready'; text: string; sha: string; verified: boolean } | { status: 'error'; error: unknown }>({ status: 'idle' });
  const load = async () => {
    setState({ status: 'loading' });
    try {
      const a = await api().artifactText(id);
      setState({ status: 'ready', text: a.text, sha: a.sha256, verified: a.hashVerified });
    } catch (error) { setState({ status: 'error', error }); }
  };
  if (state.status === 'idle') return <Button className="mt-1 !px-2 !py-0.5 text-xs" onClick={() => void load()}>View {label} <Mono>{id}</Mono></Button>;
  if (state.status === 'loading') return <Loading label={`Fetching ${id}`} />;
  if (state.status === 'error') return <div className="mt-1"><ErrorState error={state.error} onRetry={() => void load()} context={`Artifact ${id}`} /></div>;
  return (
    <div className="mt-1">
      <p className="text-faint">sha256 <Mono>{state.sha.slice(0, 16)}…</Mono> {state.verified ? '· matches server hash' : '· server sent no hash'}</p>
      {asDiff ? <DiffView diff={state.text} /> : <pre className="mt-1 max-h-80 overflow-auto whitespace-pre-wrap rounded bg-bg p-2 font-mono text-[0.75rem] text-muted">{state.text}</pre>}
    </div>
  );
}
