'use client';

import { useSession } from '@/components/session';
import { Button } from '@/components/ui';

export function UserBar() {
  const { me, signOut } = useSession();
  const org = me.memberships[0];
  return (
    <div className="mb-4 flex flex-wrap items-center justify-end gap-2 text-xs text-faint">
      <span>
        Signed in as <span className="text-ink" data-testid="signed-in-user">{me.user.github_login}</span>
        {org && <> · {org.organization.name} ({org.role})</>}
      </span>
      <Button variant="ghost" onClick={() => void signOut()}>Sign out</Button>
    </div>
  );
}
