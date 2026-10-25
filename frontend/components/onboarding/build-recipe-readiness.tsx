'use client';

import type { Repository } from '@hackatl/frontend-transport';
import { ApiError } from '@hackatl/frontend-transport';
import { Button, ErrorState, Loading, Tag } from '@/components/ui';
import { api } from '@/lib/api';
import { useResource } from '@/lib/use-resource';

type RecipeEvent = {
  action: string;
  subject_id: string;
  at: string;
  details: Record<string, unknown>;
};

function reasonText(event: RecipeEvent): string {
  return typeof event.details.reason === 'string' ? event.details.reason : 'No reason provided.';
}

function httpsUrl(value: unknown): string | null {
  if (typeof value !== 'string') return null;
  try {
    const url = new URL(value);
    return url.protocol === 'https:' ? url.toString() : null;
  } catch {
    return null;
  }
}

function Result({ event, compact }: { event: RecipeEvent; compact: boolean }) {
  if (compact) {
    const status = event.action === 'recipe.pr_opened'
      ? { label: 'PR OPENED', tone: 'info' as const }
      : event.action === 'recipe.unsupported'
        ? { label: 'UNSUPPORTED', tone: 'warn' as const }
        : event.action === 'recipe.invalid' || event.action === 'recipe.failed'
          ? { label: event.action === 'recipe.invalid' ? 'INVALID' : 'FAILED', tone: 'bad' as const }
          : event.action === 'recipe.skipped'
            ? { label: 'SKIPPED', tone: 'neutral' as const }
            : { label: 'RECIPE EVENT', tone: 'neutral' as const };
    return <Tag tone={status.tone}>{status.label}</Tag>;
  }
  if (event.action === 'recipe.pr_opened') {
    const url = httpsUrl(event.details.url);
    return (
      <div className="space-y-2">
        <Tag tone="info">PR OPENED</Tag>
        <p className="text-sm text-muted">Ari opened a pull request adding build_recipe.json. It has not run yet; the first assessment after you merge it proves it.</p>
        {url && <a className="text-sm text-brand underline-offset-2 hover:underline" href={url} target="_blank" rel="noreferrer">View pull request</a>}
      </div>
    );
  }
  if (event.action === 'recipe.skipped') return <><Tag>SKIPPED</Tag><p className="mt-2 text-sm text-muted">{reasonText(event)}</p></>;
  if (event.action === 'recipe.unsupported') return <><Tag tone="warn">UNSUPPORTED</Tag><p className="mt-2 text-sm text-muted">{reasonText(event)}</p></>;
  if (event.action === 'recipe.invalid') {
    const reasons = Array.isArray(event.details.reasons) ? event.details.reasons.filter((item): item is string => typeof item === 'string') : [];
    return <><Tag tone="bad">INVALID</Tag>{reasons.length > 0 ? <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-muted">{reasons.map((reason, i) => <li key={`${i}-${reason}`}>{reason}</li>)}</ul> : <p className="mt-2 text-sm text-muted">No validation reasons provided.</p>}</>;
  }
  if (event.action === 'recipe.failed') return <><Tag tone="bad">FAILED</Tag><p className="mt-2 text-sm text-muted">{reasonText(event)}</p></>;
  return <><Tag>RECIPE EVENT</Tag><p className="mt-2 text-sm text-muted">{event.action}</p></>;
}

export function BuildRecipeReadiness({ projectId, repo, compact = false }: { projectId: string; repo: Repository; compact?: boolean }) {
  const events = useResource(
    repo.installation_id == null ? null : `recipe-audit:${projectId}:${repo.id}`,
    signal => api().auditEvents(projectId, { signal }),
  );

  if (repo.installation_id == null) {
    return compact ? <Tag>NOT CONNECTED</Tag> : <p className="text-sm text-muted">No build recipe is proposed for repositories not connected through the GitHub App.</p>;
  }
  if (events.status === 'loading') return compact ? <span className="text-xs text-faint">Loading…</span> : <Loading label="Loading build-recipe result" />;
  if (events.status === 'error') {
    if (events.error instanceof ApiError && events.error.status === 403) {
      return compact ? <Tag tone="warn">OWNER ONLY</Tag> : <p className="text-sm text-muted">Only project owners can read the build-recipe result.</p>;
    }
    return <ErrorState error={events.error} onRetry={events.reload} context="Could not load the build-recipe result" />;
  }

  const latest = events.data.items
    .filter(event => event.action.startsWith('recipe.') && event.subject_id === repo.id)
    .sort((a, b) => Date.parse(b.at) - Date.parse(a.at))[0];
  if (!latest) {
    if (compact) return <Tag>NO RESULT YET</Tag>;
    return (
      <div className="space-y-2">
        <Tag>NO RESULT YET</Tag>
        <p className="text-sm text-muted">Ari proposes a build recipe in the background after connecting. Nothing has been recorded for this repository yet.</p>
        <Button onClick={events.reload}>Refresh</Button>
      </div>
    );
  }
  return <Result event={latest} compact={compact} />;
}
