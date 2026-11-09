'use client';

import Link from 'next/link';
import { cloneElement, isValidElement, useId, type ButtonHTMLAttributes, type ReactElement, type ReactNode } from 'react';
import { ContractSkewHint } from '@/components/contract-skew';
import { describeError } from '@/lib/api';
import type { Resource } from '@/lib/use-resource';
import type { StatusView, Tone } from '@/lib/status';
import { formatTime, relativeTime } from '@/lib/format';

const TONE: Record<Tone, string> = {
  ok: 'text-ok',
  warn: 'text-warn',
  bad: 'text-bad',
  info: 'text-info',
  accent: 'text-ember',
  neutral: 'text-muted',
};

/** Shape of the evidence mark for a status: how far the claim is proven, independent of colour. */
function markFor(view: StatusView): string {
  if (view.glyph === '⏸') return 'paused';
  if (view.glyph === '×' || view.tone === 'bad') return 'failed';
  if (view.glyph === '✓' || view.tone === 'ok') return 'done';
  if (view.glyph === '!') return 'partial';
  if (view.glyph === '◔') return 'running';
  return 'pending';
}

export function Badge({ view, title }: { view: StatusView; title?: string }) {
  const mark = markFor(view);
  return (
    <span title={title} className="status-badge inline-flex items-center gap-1.5 whitespace-nowrap text-xs text-muted">
      <span aria-hidden="true" className={`status-mark status-mark-${mark} ${TONE[view.tone]}`}>{mark === 'failed' ? '×' : null}</span>
      {view.label}
    </span>
  );
}

export function Tag({ children, tone = 'neutral' }: { children: ReactNode; tone?: Tone }) {
  return <span className={`inline-flex items-center whitespace-nowrap text-xs ${TONE[tone]}`}>{children}</span>;
}

export function Panel({ title, actions, children, className = '', id }: { title?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string; id?: string }) {
  return (
    <section id={id} className={`panel min-w-0 rounded-xl border border-line bg-panel ${className}`} aria-label={typeof title === 'string' ? title : undefined}>
      {(title || actions) && (
        <header className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-5 py-3">
          {title && <h2 className="text-sm font-medium text-ink">{title}</h2>}
          {actions && <div className="flex min-w-0 max-w-full flex-wrap items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className="p-5 sm:p-6">{children}</div>
    </section>
  );
}

export function Button({ variant = 'secondary', className = '', children, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'danger' | 'ghost' }) {
  const styles = {
    primary: 'bg-brand text-on-brand hover:bg-brand-deep',
    secondary: 'border border-line bg-panel-2 text-ink hover:border-control',
    danger: 'border border-bad/40 text-bad hover:bg-bad/10',
    ghost: 'text-muted hover:bg-panel-2 hover:text-ink',
  }[variant];
  return (
    <button
      type="button"
      data-variant={variant}
      {...props}
      className={`btn inline-flex items-center justify-center gap-1.5 rounded-lg px-3 text-sm font-medium transition-[background-color,border-color,color,transform] duration-150 ease-[var(--ease-out)] active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50 disabled:active:scale-100 ${styles} ${className}`}
    >
      {children}
    </button>
  );
}

/** Label that rolls up to a second copy on hover (the copy is hidden from assistive tech). */
export function RollText({ children }: { children: string }) {
  return (
    <span className="roll">
      <span>{children}</span>
      <span aria-hidden="true">{children}</span>
    </span>
  );
}

export function ErrorState({ error, onRetry, context }: { error: unknown; onRetry?: () => void; context?: string }) {
  const e = describeError(error);
  const signedOut = e.status === 401 || e.code === 'UNAUTHENTICATED' || e.code === 'CSRF_FAILED';
  return (
    <div role="alert" data-testid="error-state" className="rounded-md border border-bad/40 bg-bad/5 p-3 text-sm ">
      <p className="font-semibold text-bad"><span aria-hidden="true">× </span>{context ? `${context}: ` : ''}{e.title}</p>
      <p className="mt-1 text-muted">{e.detail}</p>
      {e.recovery && <p className="mt-1 text-ink" data-testid="error-recovery"><span className="font-semibold">What to do: </span>{e.recovery}</p>}
      {(e.code || e.requestId) && (
        <p className="mt-1 font-mono text-xs text-faint">
          {e.code && <>code {e.code}</>}{e.requestId && <> · request {e.requestId}</>}
        </p>
      )}
      {e.kind === 'protocol' && <ContractSkewHint />}
      {(onRetry || e.status === 403 || e.status === 404 || signedOut) && (
        <div className="mt-2 flex flex-wrap items-center gap-3">
          {/* Retrying an expired session only fails again; a full navigation re-runs the session check and shows sign-in. */}
          {/* eslint-disable-next-line @next/next/no-html-link-for-pages */}
          {signedOut && <a className="text-sm font-semibold text-brand hover:underline" href="/connect" data-testid="sign-in-again">Sign in again</a>}
          {onRetry && !signedOut && <Button onClick={onRetry}>Retry</Button>}
          {(e.status === 403 || e.status === 404) && <Link className="text-sm font-semibold text-brand hover:underline" href="/connect">Back to projects</Link>}
        </div>
      )}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="empty-state rounded-lg border border-dashed border-control/60 bg-panel-2/40 px-4 py-8 text-center text-sm text-muted">{children}</p>;
}

export function Loading({ label = 'Loading' }: { label?: string }) {
  return <p role="status" aria-live="polite" className="text-sm text-muted"><span aria-hidden="true" className="loading-dot" />{label}…</p>;
}

/** Render loading / error / ready for a resource with no silent fallbacks. */
export function Async<T>({ resource, label, children }: { resource: Resource<T>; label: string; children: (data: T) => ReactNode }) {
  if (resource.status === 'loading') return <Loading label={`Loading ${label}`} />;
  if (resource.status === 'error') return <ErrorState error={resource.error} onRetry={resource.reload} context={`Could not load ${label}`} />;
  return <>{resource.refreshError !== undefined && <StaleNotice what={label} onRetry={resource.reload} />}{children(resource.data)}</>;
}

/** Shown whenever a background refresh failed and the page is still showing the last good copy. */
export function StaleNotice({ what, onRetry }: { what: string; onRetry: () => void }) {
  return (
    <p role="status" className="mb-3 flex flex-wrap items-center gap-2 text-xs text-warn" data-testid="stale-notice">
      Could not refresh {what}. Showing the last loaded copy, which may be out of date.
      <button type="button" className="font-semibold underline-offset-2 hover:underline" onClick={onRetry}>Retry</button>
    </p>
  );
}

export function Mono({ children, className = '' }: { children: ReactNode; className?: string }) {
  // Long IDs and step keys may break anywhere so they never force sideways scrolling.
  return <code className={`font-mono text-[0.8rem] text-muted [overflow-wrap:anywhere] ${className}`}>{children}</code>;
}

export function Time({ iso }: { iso: string | null | undefined }) {
  if (!iso) return <span className="text-faint">—</span>;
  return <time dateTime={iso} title={formatTime(iso)} className="whitespace-nowrap">{relativeTime(iso)}</time>;
}

/** Label and hint are tied to the control by id, so its accessible name is only the label. */
export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactElement<{ id?: string; 'aria-describedby'?: string }> }) {
  const id = useId();
  const control = isValidElement(children) ? cloneElement(children, { id, ...(hint ? { 'aria-describedby': `${id}-hint` } : {}) }) : children;
  return (
    <div className="flex flex-col gap-1 text-sm">
      <label htmlFor={id} className="text-muted">{label}</label>
      {control}
      {hint && <span id={`${id}-hint`} className="text-xs text-faint">{hint}</span>}
    </div>
  );
}

export const inputClass = 'max-w-full rounded-md border border-control bg-bg px-2.5 py-1.5 text-sm text-ink placeholder:text-faint transition-[border-color,box-shadow] duration-200 focus:border-brand focus:shadow-[0_0_0_3px_rgba(194,69,45,0.15)] focus:outline-none';

export function Stat({ label, value, hint }: { label: string; value: ReactNode; hint?: string }) {
  return (
    <div className="rounded-lg border border-line border-t-2 border-t-brand/70 bg-panel px-4 py-3.5">
      <p className="label-mono text-faint">{label}</p>
      <p className="mt-2 font-display text-2xl font-semibold tabular-nums tracking-tight text-ink">{value}</p>
      {hint && <p className="text-xs text-muted">{hint}</p>}
    </div>
  );
}

/** Analytics-style stat row: one bordered panel, cells split by hairlines. */
export function StatGrid({ items, testId }: { items: Array<{ label: string; value: ReactNode }>; testId?: string }) {
  return (
    <div data-testid={testId} className="grid grid-cols-2 rounded-lg border border-line bg-panel sm:grid-flow-col sm:auto-cols-fr sm:grid-cols-none">
      {items.map((it, i) => (
        <div key={it.label} className={`min-w-0 px-4 py-3 ${i % 2 ? 'border-l border-line' : ''} ${i > 1 ? 'border-t border-line sm:border-t-0' : ''} ${i > 0 ? 'sm:border-l' : ''}`}>
          <p className="font-mono text-2xl font-semibold text-ink">{typeof it.value === 'number' ? it.value.toLocaleString() : it.value}</p>
          <p className="mt-1 text-xs text-muted">{it.label}</p>
        </div>
      ))}
    </div>
  );
}

/** Explanations stay available but collapsed, so the page reads like a dashboard. */
export function Details({ summary = 'How this works', children, testId }: { summary?: string; children: ReactNode; testId?: string }) {
  return (
    <details className="project-detail rounded-lg border border-line bg-panel px-4 py-3 text-sm text-muted" data-testid={testId}>
      <summary className="label-mono text-muted">{summary}</summary>
      <div className="flex flex-col gap-3">{children}</div>
    </details>
  );
}

export function Crumbs({ items }: { items: Array<{ href?: string; label: string }> }) {
  return (
    <nav aria-label="Breadcrumb" className="label-mono mb-3 text-muted">
      <ol className="flex flex-wrap items-center gap-1">
        {items.map((it, i) => (
          <li key={i} className="flex items-center gap-1">
            {i > 0 && <span aria-hidden="true" className="text-faint">/</span>}
            {it.href ? <Link className="transition-colors hover:text-brand" href={it.href}>{it.label}</Link> : <span className="text-ink">{it.label}</span>}
          </li>
        ))}
      </ol>
    </nav>
  );
}

export function PageTitle({ title, subtitle, actions }: { title: ReactNode; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="page-title mb-6 flex flex-wrap items-end justify-between gap-3 border-b border-line pb-5">
      <div className="min-w-0">
        <h1 className="text-3xl font-medium tracking-[-0.02em] text-ink">{title}</h1>
        {subtitle && <div className="mt-2 max-w-2xl text-sm text-muted">{subtitle}</div>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}
