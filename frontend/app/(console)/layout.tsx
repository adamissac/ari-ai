'use client';

import type { ReactNode } from 'react';
import { SessionGate, useSession } from '@/components/session';
import { Button } from '@/components/ui';

function UserBar() {
  const { me, signOut } = useSession();
  const org = me.memberships[0];
  return (
    <div className="mb-5 flex flex-wrap items-center justify-end gap-3 text-sm text-muted">
      <span>
        Signed in as <span className="text-ink" data-testid="signed-in-user">{me.user.github_login}</span>
        {org && <> · {org.organization.name} ({org.role})</>}
      </span>
      <Button variant="ghost" onClick={() => void signOut()}>Sign out</Button>
    </div>
  );
}

export default function ConsoleLayout({ children }: { children: ReactNode }) {
  return (
    <SessionGate>
      <UserBar />
      {children}
    </SessionGate>
  );
}
