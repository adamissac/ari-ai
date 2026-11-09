'use client';

import Link from 'next/link';
import { useDemoView } from '@/lib/demo/use-view';

export function RefreshFromGitHub({ className = '' }: { className?: string }) {
  // The demo account never starts a real GitHub sign-in.
  if (useDemoView()) return <p className={`text-xs text-muted ${className}`}>Demo account: repositories come from the sample lumen-pay installation.</p>;
  return (
    <p className={`text-xs text-muted ${className}`}>
      Added repositories to an organization?{' '}
      <Link
        href="/api/v1/auth/github/login"
        prefetch={false}
        className="text-brand underline-offset-2 hover:underline"
      >
        Refresh from GitHub
      </Link>{' '}
      to see them.
    </p>
  );
}
