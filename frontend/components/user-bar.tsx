'use client';

import { useState } from 'react';
import { useSession } from '@/components/session';
import { Button, ErrorState } from '@/components/ui';

export function UserBar() {
  const { me, signOut } = useSession();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const org = me.memberships[0];
  // If the backend did not end the session, the user is still signed in: say so instead of failing silently.
  const onSignOut = async () => {
    setBusy(true);
    setError(null);
    try { await signOut(); } catch (err) { setError(err); setBusy(false); }
  };
  return (
    <div className="mb-4 flex flex-col items-end gap-2">
      <div className="flex flex-wrap items-center justify-end gap-2 text-xs text-faint">
        <span>
          Signed in as <span className="text-ink" data-testid="signed-in-user">{me.user.github_login}</span>
          {org && <> · {org.organization.name} ({org.role})</>}
        </span>
        <Button variant="ghost" disabled={busy} onClick={() => void onSignOut()}>Sign out</Button>
      </div>
      {error !== null && <ErrorState error={error} onRetry={() => void onSignOut()} context="Sign out failed; you are still signed in" />}
    </div>
  );
}
