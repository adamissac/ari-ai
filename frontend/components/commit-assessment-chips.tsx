'use client';

import type { Assessment } from '@hackatl/frontend-transport';
import Link from 'next/link';
import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { Badge } from '@/components/ui';
import { api } from '@/lib/api';
import { projectForRepository } from '@/lib/github-connect';
import { commitOutcome, type CommitOutcome } from '@/lib/findings';
import { ASSESSMENT_STATE, type StatusView } from '@/lib/status';

type Lookup =
  | { status: 'loading' | 'error'; repoId: string }
  | { status: 'ready'; repoId: string; projectId: string; items: Assessment[]; truncated: boolean };

const LookupContext = createContext<Lookup | null>(null);

export function CommitAssessmentProvider({ repoId, children }: { repoId: string; children: ReactNode }) {
  const [lookup, setLookup] = useState<Lookup>({ status: 'loading', repoId });
  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    void (async () => {
      const projectId = await projectForRepository(repoId, controller.signal);
      const items: Assessment[] = [];
      let cursor: string | undefined;
      let pages = 0;
      do {
        const page = await api().assessments(projectId, { cursor, repoId, signal: controller.signal });
        items.push(...page.items);
        cursor = page.next_cursor ?? undefined;
        pages += 1;
      } while (cursor && pages < 3);
      if (active) setLookup({ status: 'ready', repoId, projectId, items, truncated: cursor !== undefined });
    })().catch(() => {
      if (active) setLookup({ status: 'error', repoId });
    });
    return () => {
      active = false;
      controller.abort();
    };
  }, [repoId]);

  const currentLookup = lookup.repoId === repoId ? lookup : { status: 'loading' as const, repoId };
  return <LookupContext.Provider value={currentLookup}>{children}</LookupContext.Provider>;
}

/** A finished review reads as what it found, not as a run state. */
export function outcomeViews(o: CommitOutcome): StatusView[] {
  const views: StatusView[] = [];
  if (o.needsFix) views.push({ label: `${o.needsFix} need${o.needsFix === 1 ? 's' : ''} a fix`, tone: 'warn', glyph: '!' });
  if (o.fixed) views.push({ label: `${o.fixed} fixed`, tone: 'ok', glyph: '✓' });
  if (!views.length) views.push({ label: o.unproven ? 'No proven issues' : 'No issues found', tone: 'ok', glyph: '✓' });
  return views;
}

export function CommitAssessmentChip({ repoId, sha, committedAt, findings }: {
  repoId: string; sha: string; committedAt?: string | null;
  /** The repository's findings; with them a completed review shows its outcome. */
  findings?: readonly { assessment_id: string; status: string }[];
}) {
  const lookup = useContext(LookupContext);
  if (!lookup || lookup.status !== 'ready' || lookup.truncated) return null;
  const matches = lookup.items
    .filter(assessment => assessment.repo_id === repoId && assessment.commit_sha === sha)
    .sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at));
  const newest = matches[0];
  if (!newest) {
    // Ari reviews commits from the moment a repository is connected; it does not go back over history.
    const first = lookup.items.filter(a => a.repo_id === repoId).reduce<number | null>((min, a) => Math.min(min ?? Infinity, Date.parse(a.created_at)), null);
    const before = committedAt != null && (first === null || Date.parse(committedAt) < first);
    return <span data-testid="not-reviewed" className="font-mono text-xs text-faint">{before ? 'Before Ari was connected' : 'Not reviewed'}</span>;
  }
  const status = ASSESSMENT_STATE[newest.state];
  if (!status) return null;
  const views = newest.state === 'COMPLETED' && findings ? outcomeViews(commitOutcome(findings, newest.id)) : [status];
  const additionalCount = matches.length - 1;
  const additionalDescription = `${additionalCount} more assessment${additionalCount === 1 ? '' : 's'} of this commit`;
  return (
    <>
      <Link
        href={`/projects/${lookup.projectId}/assessments/${newest.id}?repo=${encodeURIComponent(repoId)}`}
        aria-label={`${views.map(view => view.label).join(', ')} assessment`}
        data-testid="commit-assessment-status"
        className="inline-flex gap-1.5"
      >
        {views.map(view => <Badge key={view.label} view={view} />)}
      </Link>
      {additionalCount > 0 && (
        <span
          className="font-mono text-xs text-muted"
          data-testid="other-assessments"
          title={additionalDescription}
          aria-label={additionalDescription}
        >
          +{additionalCount}
        </span>
      )}
    </>
  );
}
