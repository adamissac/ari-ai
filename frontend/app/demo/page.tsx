'use client';

import Link from 'next/link';
import { BRAND_NAME } from '@/components/brand';
import { RecordedLiveRun } from '@/components/demo/recorded-live-run';
import { Avatar, DemoBar } from '@/components/demo/ui';
import { DEMO_ORGS, reposFor } from '@/lib/demo/data';
import { useDemoSession } from '@/lib/demo/session';

export default function DemoOrgsPage() {
  const { user, ready, signOut } = useDemoSession();

  if (!ready || !user) return <div className="min-h-[60vh]" />;

  return (
    <div data-testid="demo-orgs">
      <DemoBar crumbs={[{ label: 'Choose an organization' }]} user={user} onSignOut={signOut} />
      <header className="mb-6">
        <p className="label-mono text-brand">Signed in as {user.login}</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">Where should {BRAND_NAME} look?</h1>
        <p className="mt-1.5 text-sm text-muted">Pick an organization. You can connect more later from settings.</p>
      </header>
      <ul className="grid gap-3 md:grid-cols-3">
        {DEMO_ORGS.map((org, i) => {
          const repos = reposFor(org.login);
          return (
            <li key={org.login} className="demo-rise" style={{ ['--i' as string]: i }}>
              <Link href={`/demo/${org.login}`} className="demo-card group flex h-full flex-col gap-4 p-5" data-testid={`demo-org-${org.login}`}>
                <span className="flex items-center gap-3">
                  <Avatar login={org.login} size={40} />
                  <span className="min-w-0">
                    <span className="block truncate font-semibold">{org.name}</span>
                    <span className="block truncate font-mono text-xs text-muted">{org.login}</span>
                  </span>
                </span>
                <span className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
                  <span>{repos.length} {repos.length === 1 ? 'repository' : 'repositories'}</span>
                  <span>{org.members} {org.members === 1 ? 'member' : 'members'}</span>
                  <span>{org.kind === 'personal' ? 'Personal account' : `${org.plan} plan`}</span>
                </span>
                <span className="mt-auto text-sm font-medium text-brand">Open <span aria-hidden="true" className="inline-block transition-transform group-hover:translate-x-1">→</span></span>
              </Link>
            </li>
          );
        })}
      </ul>
      <RecordedLiveRun />
    </div>
  );
}
