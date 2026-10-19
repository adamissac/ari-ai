'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { CommitAnalysis } from '@/components/demo/commit-analysis';
import { Empty, ErrorState, Loading } from '@/components/ui';
import type { DemoCommit, DemoRepo } from '@/lib/demo/data';
import type { LiveResult } from '@/lib/live-analysis';
import { minutesSince } from '@/lib/simulated-attack';
import { useAccessibleRepo } from '@/lib/real-repo';

type Live = { status: 'loading' } | { status: 'error'; message: string } | { status: 'ready'; data: LiveResult };

/**
 * A real commit from the user's repository, analysed live: the diff comes from GitHub and the
 * code review plus the seven agents' reasoning come from Claude over that diff (lib/live-analysis.ts).
 * Static analysis only: nothing is run or attacked, and the page says so.
 */
export default function RealCommitPage() {
  const params = useParams<{ org: string; repo: string; sha: string }>();
  const org = decodeURIComponent(params.org);
  const name = decodeURIComponent(params.repo);
  const repo = useAccessibleRepo(org, name);
  const full = repo.status === 'ready' && repo.data ? repo.data.full_name : null;
  const [live, setLive] = useState<Live>({ status: 'loading' });
  const [attempt, setAttempt] = useState(0);
  const retry = useCallback(() => { setLive({ status: 'loading' }); setAttempt(n => n + 1); }, []);

  useEffect(() => {
    if (!full) return;
    const ctrl = new AbortController();
    fetch('/api/analyze', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ repo: full, sha: params.sha }), signal: ctrl.signal })
      .then(async res => {
        const body = await res.json().catch(() => null);
        if (!res.ok) throw new Error(body?.error?.message ?? `Live analysis failed (${res.status}).`);
        setLive({ status: 'ready', data: body as LiveResult });
      })
      .catch((error: unknown) => { if (!ctrl.signal.aborted) setLive({ status: 'error', message: error instanceof Error ? error.message : 'Live analysis failed.' }); });
    return () => ctrl.abort();
  }, [full, params.sha, attempt]);

  const view = useMemo(() => {
    if (live.status !== 'ready' || !repo.data) return null;
    const { data } = live;
    const commit: DemoCommit = {
      sha: data.commit.sha,
      message: data.commit.message,
      body: data.commit.body,
      author: data.commit.author,
      minutesAgo: minutesSince(data.commit.committedAt),
      branch: repo.data.default_branch,
      ci: 'pending',
      verdict: data.verdict,
      scenario: 'clean',
      files: data.commit.files,
      additions: data.commit.additions,
      deletions: data.commit.deletions,
    };
    const demoRepo: DemoRepo = {
      org, name, description: '', language: '', visibility: repo.data.private ? 'private' : 'public', defaultBranch: repo.data.default_branch,
      stars: 0, components: data.components, links: data.links, commits: [commit],
    };
    return { commit, repo: demoRepo, analysis: data.analysis, live: { model: data.model, truncated: data.truncated, htmlUrl: data.commit.htmlUrl } };
  }, [live, repo.data, org, name]);

  return (
    <div className="commit-stage" data-testid="real-commit">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <nav aria-label="Breadcrumb" className="flex flex-wrap items-center gap-1.5 text-sm">
          <Link href="/connect">Organizations</Link><span aria-hidden="true" className="text-white/30">/</span>
          <Link href={`/connect/${encodeURIComponent(org)}`}>{org}</Link><span aria-hidden="true" className="text-white/30">/</span>
          <Link href={`/connect/${encodeURIComponent(org)}/${encodeURIComponent(name)}`}>{name}</Link><span aria-hidden="true" className="text-white/30">/</span>
          <span className="font-semibold">{params.sha.slice(0, 7)}</span>
        </nav>
        <details className="amap-more text-right" data-testid="real-commit-note">
          <summary><span className="demo-marker" data-testid="real-commit-provenance" title="The diff comes from GitHub. The review and agent results come from a live Claude analysis of that diff.">Live analysis · real commit</span> What is real here?</summary>
          <p className="mt-2 max-w-sm text-left text-xs text-white/60">
            The commit and its diff come from GitHub. The code review, findings, proposed fix and each agent&apos;s steps are a live
            analysis of that diff by {view?.live.model ?? 'Claude'}{live.status === 'ready' ? `, run in ${live.data.analysis.seconds}s for about $${live.data.analysis.usd.toFixed(2)}` : ''}.
            It is static: no code was run, nothing was attacked, the proposed tests have not been executed and no fix was applied.
            The agent view replays that run step by step.
          </p>
        </details>
      </div>
      {repo.status === 'loading' && <Loading label="Loading the repository" />}
      {repo.status === 'error' && <ErrorState error={repo.error} onRetry={repo.reload} />}
      {repo.status === 'ready' && !repo.data && <Empty>{org}/{name} is not reachable through your GitHub App installation.</Empty>}
      {full && live.status === 'loading' && <Loading label="Reading the diff and running the review and the seven agents (this takes a minute or two)" />}
      {live.status === 'error' && (
        <div className="glass flex flex-col items-start gap-3 p-6" role="alert">
          <p className="text-sm text-white/80">{live.message}</p>
          <button type="button" onClick={retry} className="rounded-full bg-white px-4 py-2 text-sm font-medium text-ink">Try again</button>
        </div>
      )}
      {view?.live.truncated && <p className="mb-4 text-xs text-white/55">This commit is large: only the first part of its diff was analysed.</p>}
      {view && <CommitAnalysis key={view.commit.sha} repo={view.repo} commit={view.commit} analysis={view.analysis} live={view.live} />}
    </div>
  );
}
