'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { Avatar, CiBadge, DemoBar, VerdictChip } from '@/components/demo/ui';
import { Empty } from '@/components/ui';
import { CONNECTED_DAYS_AGO, DEMO_ORGS, findRepo, relativeTime, type DemoCommit } from '@/lib/demo/data';
import { useDemoGate } from '@/lib/demo/gate';

/** Groups commits under "Today", "Yesterday" and "Earlier", like a commit history page. */
function groups(commits: DemoCommit[]): { label: string; items: DemoCommit[] }[] {
  const buckets = [
    { label: 'Today', items: commits.filter(c => c.minutesAgo < 24 * 60) },
    { label: 'Yesterday', items: commits.filter(c => c.minutesAgo >= 24 * 60 && c.minutesAgo < 48 * 60) },
    { label: 'Earlier this week', items: commits.filter(c => c.minutesAgo >= 48 * 60) },
  ];
  return buckets.filter(b => b.items.length > 0);
}

export default function DemoCommitsPage() {
  const { org, repo: name } = useParams<{ org: string; repo: string }>();
  const session = useDemoGate();
  if (!session.user) return <div className="min-h-[60vh]" />;
  const repo = findRepo(org, name);
  const orgName = DEMO_ORGS.find(o => o.login === org)?.name ?? org;
  if (!repo) return <Empty>Repository not found.</Empty>;
  const caught = repo.commits.filter(c => c.verdict === 'fixed').length;

  return (
    <div data-testid="demo-commits">
      <DemoBar crumbs={[{ href: '/demo', label: 'Organizations' }, { href: `/demo/${org}`, label: orgName }, { label: repo.name }]} user={session.user} onSignOut={session.signOut} />
      <header className="demo-ink mb-6 rounded-3xl px-6 py-7 md:px-9">
        <p className="label-mono text-white/60">{org} / {repo.name}</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">Commits since {orgName} connected Ari</h1>
        <p className="mt-1.5 max-w-2xl text-sm text-white/70">Connected {CONNECTED_DAYS_AGO} days ago. Every push since then was reviewed and checked by the seven agents. Open a commit to replay it.</p>
        <dl className="mt-6 grid max-w-2xl grid-cols-3 gap-4">
          <div><dt className="label-mono text-white/50">Commits analyzed</dt><dd className="mt-1 font-display text-2xl font-semibold">{repo.commits.length}</dd></div>
          <div><dt className="label-mono text-white/50">Issues fixed</dt><dd className="mt-1 font-display text-2xl font-semibold">{caught}</dd></div>
          <div><dt className="label-mono text-white/50">Watching</dt><dd className="mt-1 font-display text-2xl font-semibold">{repo.components.length} <span className="text-sm font-normal text-white/60">components</span></dd></div>
        </dl>
      </header>
      {groups(repo.commits).map(group => (
        <section key={group.label} className="mb-6">
          <h2 className="label-mono mb-2 text-faint">{group.label}</h2>
          <ol className="overflow-hidden rounded-2xl border border-line bg-white">
            {group.items.map((commit, i) => (
              <li key={commit.sha} className="demo-rise border-b border-line last:border-b-0" style={{ ['--i' as string]: i }}>
                <Link href={`/demo/${org}/${repo.name}/commit/${commit.sha}`} className="group grid gap-3 px-5 py-4 transition-colors hover:bg-panel-2 md:grid-cols-[minmax(0,1fr)_auto] md:items-center" data-testid="demo-commit-row">
                  <span className="flex min-w-0 gap-3">
                    <Avatar login={commit.author} size={30} />
                    <span className="min-w-0">
                      <span className="block truncate font-medium group-hover:text-brand">{commit.message}</span>
                      <span className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
                        <span className="font-semibold text-ink">{commit.author}</span>
                        <span suppressHydrationWarning>committed {relativeTime(commit.minutesAgo)}</span>
                        {commit.branch !== repo.defaultBranch && <span className="rounded bg-panel-2 px-1.5 py-0.5 font-mono">{commit.branch}</span>}
                        <span><span className="text-ok">+{commit.additions}</span> <span className="text-bad">−{commit.deletions}</span> in {commit.files} file{commit.files === 1 ? '' : 's'}</span>
                        <CiBadge state={commit.ci} />
                      </span>
                    </span>
                  </span>
                  <span className="flex items-center gap-3 pl-[42px] md:pl-0">
                    <VerdictChip verdict={commit.verdict} />
                    <span className="rounded-md border border-line px-2 py-1 font-mono text-xs text-muted group-hover:border-brand/40">{commit.sha.slice(0, 7)}</span>
                  </span>
                </Link>
              </li>
            ))}
          </ol>
        </section>
      ))}
    </div>
  );
}
