'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useState, type FormEvent } from 'react';
import { AuthStage, LockIcon } from '@/components/auth-stage';
import { BRAND_NAME } from '@/components/brand';

/** Sign in to the demo account with an access code (checked on the server). */
export function AccessForm({ next }: { next: string }) {
  const router = useRouter();
  const [code, setCode] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await fetch('/api/demo-session', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code }),
      });
      if (res.ok) {
        router.replace(next);
        return;
      }
      const body = (await res.json().catch(() => ({}))) as { error?: string };
      setError(body.error ?? 'Sign-in failed.');
    } catch {
      setError('Could not reach the server. Try again.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthStage
      title="Sign in with an access code"
      subtitle={`For workspaces set up by the ${BRAND_NAME} team.`}
      testId="access-signin"
      footnote={<><LockIcon /><span>Codes are checked on the server and never stored in your browser.</span></>}
    >
      <form onSubmit={submit} aria-label="Access code sign-in">
        <label htmlFor="access-code" className="auth-label">Access code</label>
        <input
          id="access-code"
          className="auth-input"
          type="password"
          name="access_code"
          autoComplete="current-password"
          placeholder="••••••••••"
          value={code}
          onChange={e => setCode(e.target.value)}
          required
          autoFocus
          data-testid="access-code"
        />
        {error && <p className="auth-error" role="alert" data-testid="access-error">{error}</p>}
        <button type="submit" className="auth-btn auth-btn-brand mt-5" disabled={busy || !code.trim()} data-testid="access-submit">
          {busy ? <><span aria-hidden="true" className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />Signing in</> : <>Continue <span aria-hidden="true">→</span></>}
        </button>
      </form>
      <p className="mt-6 text-center text-[13px] text-white/60">
        Have a GitHub account? <Link href="/projects" className="auth-link">Sign in with GitHub</Link>
      </p>
    </AuthStage>
  );
}
