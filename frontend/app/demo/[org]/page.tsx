'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { Avatar, DemoBar, VerdictChip } from '@/components/demo/ui';
import { Empty } from '@/components/ui';
import { CONNECTED_DAYS_AGO, DEMO_ORGS, relativeTime, reposFor } from '@/lib/demo/data';
import { useDemoGate } from '@/lib/demo/gate';

const LANG_DOT: Record<string, string> = { Python: '#3572A5', TypeScript: '#3178c6', Rust: '#dea584', Go: '#00ADD8' };

export default function DemoReposPage() {
  const { org: login } = useParams<{ org: string }>();
  const session = useDemoGate();
  if (!session.user) return <div className="min-h-[60vh]" />;
  const org = DEMO_ORGS.find(o => o.login === login);
  const repos = reposFor(login);

  return (
    <div data-testid="demo-repos">
      <DemoBar crumbs={[{ href: '/demo', label: 'Organizations' }, { label: org?.name ?? login }]} user={session.user} onSignOut={session.signOut} />
      <header className="mb-6 flex flex-wrap items-center gap-4">
        <Avatar login={login} size={48} />
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">{org?.name ?? login}</h1>
          <p className="mt-0.5 text-sm text-muted">Connected to Ari {CONNECTED_DAYS_AGO} days ago · {repos.length} {repos.length === 1 ? 'repository' : 'repositories'} watched. Open one to see every commit since.</p>
        </div>
      </header>
      {repos.length === 0 ? <Empty>No repositories in this organization.</Empty> : (
        <ul className="flex flex-col gap-2.5">
          {repos.map((repo, i) => {
            const head = repo.commits[0]!;
            const findings = repo.commits.filter(c => c.verdict === 'fixed' || c.verdict === 'needs_review').length;
            return (
              <li key={repo.name} className="demo-rise" style={{ ['--i' as string]: i }}>
                <Link href={`/demo/${login}/${repo.name}`} className="demo-card group grid gap-3 p-5 md:grid-cols-[minmax(0,1fr)_auto] md:items-center" data-testid={`demo-repo-${repo.name}`}>
                  <span className="min-w-0">
                    <span className="flex flex-wrap items-center gap-2">
                      <span className="font-semibold group-hover:text-brand">{repo.name}</span>
                      <span className="rounded-full border border-line px-2 py-0.5 text-[0.68rem] text-muted">{repo.visibility}</span>
                    </span>
                    <span className="mt-1 block text-sm text-muted">{repo.description}</span>
                    <span className="mt-2.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted">
                      <span className="flex items-center gap-1.5"><span aria-hidden="true" className="h-2.5 w-2.5 rounded-full" style={{ background: LANG_DOT[repo.language] ?? '#999' }} />{repo.language}</span>
                      <span>★ {repo.stars}</span>
                      <span>Last push {relativeTime(head.minutesAgo)}</span>
                      <span>{repo.commits.length} recent commits</span>
                    </span>
                  </span>
                  <span className="flex flex-col items-start gap-1.5 md:items-end">
                    <VerdictChip verdict={head.verdict} />
                    <span className="text-xs text-faint">{findings} issue{findings === 1 ? '' : 's'} caught recently</span>
                  </span>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
