'use client';

import { ApiError, type MeResponse } from '@hackatl/frontend-transport';
import { createContext, useCallback, useContext, useEffect, useState, type FormEvent, type ReactNode } from 'react';
import Link from 'next/link';
import { api } from '@/lib/api';
import { BRAND_NAME, BRAND_TAGLINE, Wordmark } from '@/components/brand';
import { INTRO_KEY } from '@/components/intro-loader';
import { Button, ErrorState, Field, inputClass, Loading, RollText } from '@/components/ui';

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

/** The session if one is known here, else null. For public pages that only decorate a signed-in view. */
export function useOptionalSession(): SessionValue | null {
  return useContext(SessionContext);
}

/**
 * Public pages: render children immediately for everyone. In the background, look
 * for an existing session and, only if there is one, provide it (so a "signed in as"
 * bar can appear). Signed-out visitors, or a backend that is down, see the page as is.
 */
export function OptionalSession({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<MeResponse | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    api().session({ signal: controller.signal }).then(setMe, () => { /* public page: no session is fine */ });
    return () => controller.abort();
  }, []);
  const refresh = useCallback(() => { api().session().then(setMe, () => setMe(null)); }, []);
  const signOut = useCallback(async () => {
    await api().logout();
    try { window.sessionStorage.removeItem(INTRO_KEY); } catch { /* storage unavailable */ }
    setMe(null);
  }, []);
  if (!me) return <>{children}</>;
  return <SessionContext.Provider value={{ me, refresh, signOut }}>{children}</SessionContext.Provider>;
}

const devLoginVisible = process.env.NEXT_PUBLIC_DEV_LOGIN === '1';

/** Children render only for a backend-confirmed session; offline is an explicit error. */
export function SessionGate({ children }: { children: ReactNode }) {
  const [state, setState] = useState<SessionState>({ status: 'loading' });
  const [nonce, setNonce] = useState(0);
  const refresh = useCallback(() => setNonce(n => n + 1), []);

  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    // The API restarts briefly on every deploy: retry a few times before showing an error.
    const attempt = (left: number) => api().session({ signal: controller.signal }).then(
      me => setState({ status: 'signed-in', me }),
      (error: unknown) => {
        if (controller.signal.aborted) return;
        if (error instanceof ApiError && error.status === 401) return setState({ status: 'signed-out' });
        if (left > 0 && (!(error instanceof ApiError) || error.status >= 500)) {
          timer = setTimeout(() => void attempt(left - 1), 2000);
          return;
        }
        setState({ status: 'error', error });
      },
    );
    void attempt(4);
    return () => { controller.abort(); if (timer) clearTimeout(timer); };
  }, [nonce]);

  const signOut = useCallback(async () => {
    await api().logout();
    try { window.sessionStorage.removeItem(INTRO_KEY); } catch { /* storage unavailable */ }
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
    <div className="signin-card mx-auto mt-12 grid max-w-4xl overflow-hidden rounded-2xl border border-line bg-panel shadow-[0_24px_60px_-30px_rgba(194,69,45,0.45)] md:grid-cols-2">
      <div className="hero-ink hidden flex-col justify-between p-8 md:flex">
        <Wordmark className="text-white" />
        <div>
          <p className="label-mono text-white/60">Software assurance</p>
          <p className="display mt-3 text-3xl font-semibold">A fix counts only when independent tests accept it.</p>
          <p className="mt-3 text-sm text-white/70">{BRAND_TAGLINE}</p>
        </div>
      </div>
      <div className="p-8">
      <p className="label-mono text-brand">Welcome to {BRAND_NAME}</p>
      <h1 className="mt-2 text-2xl font-semibold tracking-tight">Sign in</h1>
      <p className="mt-1 text-sm text-muted">Sessions are issued by the control-plane backend. No token is stored in the browser.</p>
      {/* OAuth must be a full browser navigation to the backend (proxied), not client routing. */}
      {/* eslint-disable-next-line @next/next/no-html-link-for-pages */}
      <a href="/api/v1/auth/github/login" className="group label-mono mt-6 flex h-10 w-full items-center justify-center rounded-md bg-brand px-3 text-on-brand shadow-[0_6px_16px_-8px_rgba(194,69,45,0.6)] transition-colors duration-[250ms] hover:bg-brand-deep">
        <RollText>Continue with GitHub</RollText>
      </a>
      <p className="mt-3 text-center text-xs text-muted">
        Have an access code? <Link href="/access" className="text-brand underline-offset-2 hover:underline" data-testid="access-link">Sign in with it</Link>
      </p>
      {devLoginVisible && (
        <form onSubmit={submit} className="mt-6 border-t border-line pt-4" aria-label="Development login">
          <p className="label-mono mb-2 text-warn">Development login — local backend only</p>
          <Field label="GitHub login">
            <input className={inputClass} value={login} onChange={e => setLogin(e.target.value)} required pattern="(?:[A-Za-z0-9]|-){1,39}" autoComplete="username" name="github_login" />
          </Field>
          <Button type="submit" variant="secondary" className="mt-3 w-full" disabled={busy || !login.trim()}>Development sign-in</Button>
          {error !== null && <div className="mt-3"><ErrorState error={error} context="Sign-in failed" /></div>}
        </form>
      )}
      </div>
    </div>
  );
}
