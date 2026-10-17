'use client';

import { ApiError, type MeResponse } from '@hackatl/frontend-transport';
import { createContext, useCallback, useContext, useEffect, useState, type FormEvent, type ReactNode } from 'react';
import { api } from '@/lib/api';
import { Button, ErrorState, Field, inputClass, Loading } from '@/components/ui';

type SessionState =
  | { status: 'loading' }
  | { status: 'signed-out' }
  | { status: 'signed-in'; me: MeResponse }
  | { status: 'error'; error: unknown };

interface SessionValue { me: MeResponse; refresh: () => void; signOut: () => Promise<void> }
const SessionContext = createContext<SessionValue | null>(null);

export function useSession(): SessionValue {
  const value = useContext(SessionContext);
  if (!value) throw new Error('useSession outside SessionGate');
  return value;
}

const devLoginVisible = process.env.NEXT_PUBLIC_DEV_LOGIN === '1';

/** Children render only for a backend-confirmed session; offline is an explicit error. */
export function SessionGate({ children }: { children: ReactNode }) {
  const [state, setState] = useState<SessionState>({ status: 'loading' });
  const [nonce, setNonce] = useState(0);
  const refresh = useCallback(() => setNonce(n => n + 1), []);

  useEffect(() => {
    const controller = new AbortController();
    api().session({ signal: controller.signal }).then(
      me => setState({ status: 'signed-in', me }),
      (error: unknown) => {
        if (controller.signal.aborted) return;
        setState(error instanceof ApiError && error.status === 401 ? { status: 'signed-out' } : { status: 'error', error });
      },
    );
    return () => controller.abort();
  }, [nonce]);

  const signOut = useCallback(async () => {
    await api().logout();
    setState({ status: 'signed-out' });
  }, []);

  if (state.status === 'loading') return <div className="mx-auto max-w-md p-10"><Loading label="Checking session" /></div>;
  if (state.status === 'error') {
    return (
      <div className="mx-auto max-w-lg p-10">
        <ErrorState error={state.error} onRetry={refresh} context="Session check failed" />
      </div>
    );
  }
  if (state.status === 'signed-out') return <SignIn onSignedIn={me => setState({ status: 'signed-in', me })} />;
  return <SessionContext.Provider value={{ me: state.me, refresh, signOut }}>{children}</SessionContext.Provider>;
}

function SignIn({ onSignedIn }: { onSignedIn: (me: MeResponse) => void }) {
  const [login, setLogin] = useState('');
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try { onSignedIn(await api().devLogin({ github_login: login.trim(), display_name: null })); }
    catch (err) { setError(err); }
    finally { setBusy(false); }
  };
  return (
    <div className="mx-auto mt-16 max-w-md rounded-lg border border-line bg-panel p-6">
      <h1 className="text-lg font-semibold">Sign in</h1>
      <p className="mt-1 text-sm text-muted">Sessions are issued by the control-plane backend. No token is stored in the browser.</p>
      {/* OAuth must be a full browser navigation to the backend (proxied), not client routing. */}
      {/* eslint-disable-next-line @next/next/no-html-link-for-pages */}
      <a href="/api/v1/auth/github/login" className="mt-4 flex w-full items-center justify-center rounded-md bg-accent px-3 py-2 text-sm font-semibold text-bg hover:bg-accent/90">
        Continue with GitHub
      </a>
      {devLoginVisible && (
        <form onSubmit={submit} className="mt-6 border-t border-line pt-4" aria-label="Development login">
          <p className="mb-2 text-xs uppercase tracking-wider text-warn">Development login — local backend only</p>
          <Field label="GitHub login">
            <input className={inputClass} value={login} onChange={e => setLogin(e.target.value)} required pattern="[A-Za-z0-9-]{1,39}" autoComplete="username" name="github_login" />
          </Field>
          <Button type="submit" variant="secondary" className="mt-3 w-full" disabled={busy || !login.trim()}>Development sign-in</Button>
          {error !== null && <div className="mt-3"><ErrorState error={error} context="Sign-in failed" /></div>}
        </form>
      )}
    </div>
  );
}
