'use client';

import Link from 'next/link';

export function RefreshFromGitHub({ className = '' }: { className?: string }) {
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
