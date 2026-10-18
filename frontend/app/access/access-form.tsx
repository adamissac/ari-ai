'use client';

import { useRouter } from 'next/navigation';
import { useState, type FormEvent } from 'react';
import { BRAND_NAME, BRAND_TAGLINE, Wordmark } from '@/components/brand';
import { Button, Field, inputClass } from '@/components/ui';

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
    <div className="signin-card mx-auto mt-12 grid max-w-4xl overflow-hidden rounded-2xl border border-line bg-panel shadow-[0_24px_60px_-30px_rgba(194,69,45,0.45)] md:grid-cols-2" data-testid="access-signin">
      <div className="hero-ink hidden flex-col justify-between p-8 md:flex">
        <Wordmark className="text-white" />
        <div>
          <p className="label-mono text-white/60">Software assurance</p>
          <p className="display mt-3 text-3xl font-semibold">A fix counts only when independent tests accept it.</p>
          <p className="mt-3 text-sm text-white/70">{BRAND_TAGLINE}</p>
        </div>
      </div>
      <form onSubmit={submit} className="p-8" aria-label="Access code sign-in">
        <p className="label-mono text-brand">Welcome to {BRAND_NAME}</p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">Sign in with an access code</h1>
        <p className="mt-1 text-sm text-muted">For accounts set up by the {BRAND_NAME} team.</p>
        <div className="mt-6">
          <Field label="Access code">
            <input
              className={inputClass}
              type="password"
              name="access_code"
              autoComplete="current-password"
              value={code}
              onChange={e => setCode(e.target.value)}
              required
              data-testid="access-code"
            />
          </Field>
        </div>
        <Button type="submit" variant="primary" className="mt-4 w-full" disabled={busy || !code.trim()} data-testid="access-submit">
          {busy ? 'Signing in…' : 'Sign in'}
        </Button>
        {error && <p className="mt-3 text-sm text-bad" role="alert" data-testid="access-error">{error}</p>}
      </form>
    </div>
  );
}
