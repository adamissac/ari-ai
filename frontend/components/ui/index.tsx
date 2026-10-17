'use client';

import Link from 'next/link';
import type { ButtonHTMLAttributes, ReactNode } from 'react';
import { describeError } from '@/lib/api';
import type { Resource } from '@/lib/use-resource';
import type { StatusView, Tone } from '@/lib/status';
import { formatTime, relativeTime } from '@/lib/format';

const TONE: Record<Tone, string> = {
  ok: 'border-ok/40 bg-ok/10 text-ok',
  warn: 'border-warn/40 bg-warn/10 text-warn',
  bad: 'border-bad/40 bg-bad/10 text-bad',
  info: 'border-info/40 bg-info/10 text-info',
  accent: 'border-accent/40 bg-accent/10 text-accent',
  neutral: 'border-line bg-panel-2 text-muted',
};

export function Badge({ view, title }: { view: StatusView; title?: string }) {
  return (
    <span title={title} className={`inline-flex items-center gap-1 whitespace-nowrap rounded border px-1.5 py-0.5 text-xs font-medium ${TONE[view.tone]}`}>
      <span aria-hidden="true">{view.glyph}</span>
      {view.label}
    </span>
  );
}

export function Tag({ children, tone = 'neutral' }: { children: ReactNode; tone?: Tone }) {
  return <span className={`inline-flex items-center rounded border px-1.5 py-0.5 text-xs ${TONE[tone]}`}>{children}</span>;
}

export function Panel({ title, actions, children, className = '', id }: { title?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string; id?: string }) {
  return (
    <section id={id} className={`rounded-lg border border-line bg-panel ${className}`} aria-label={typeof title === 'string' ? title : undefined}>
      {(title || actions) && (
        <header className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-2.5">
          {title && <h2 className="text-sm font-semibold tracking-wide text-ink">{title}</h2>}
          {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}

export function Button({ variant = 'secondary', className = '', ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'danger' | 'ghost' }) {
  const styles = {
    primary: 'bg-accent text-bg hover:bg-accent/90 font-semibold',
    secondary: 'border border-line bg-panel-2 text-ink hover:border-accent/60',
    danger: 'border border-bad/50 bg-bad/10 text-bad hover:bg-bad/20',
    ghost: 'text-muted hover:text-ink',
  }[variant];
  return <button type="button" {...props} className={`inline-flex items-center justify-center gap-1.5 rounded-md px-3 py-1.5 text-sm transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${styles} ${className}`} />;
}

export function ErrorState({ error, onRetry, context }: { error: unknown; onRetry?: () => void; context?: string }) {
  const e = describeError(error);
  return (
    <div role="alert" className="rounded-md border border-bad/40 bg-bad/5 p-3 text-sm">
      <p className="font-semibold text-bad"><span aria-hidden="true">× </span>{context ? `${context}: ` : ''}{e.title}</p>
      <p className="mt-1 text-muted">{e.detail}</p>
      {(e.code || e.requestId) && (
        <p className="mt-1 font-mono text-xs text-faint">
          {e.code && <>code {e.code}</>}{e.requestId && <> · request {e.requestId}</>}
        </p>
      )}
      {onRetry && <Button className="mt-2" onClick={onRetry}>Retry</Button>}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="rounded-md border border-dashed border-line px-3 py-4 text-center text-sm text-muted">{children}</p>;
}

export function Loading({ label = 'Loading' }: { label?: string }) {
  return <p role="status" aria-live="polite" className="animate-pulse text-sm text-muted">{label}…</p>;
}

/** Render loading / error / ready for a resource with no silent fallbacks. */
export function Async<T>({ resource, label, children }: { resource: Resource<T>; label: string; children: (data: T) => ReactNode }) {
  if (resource.status === 'loading') return <Loading label={`Loading ${label}`} />;
  if (resource.status === 'error') return <ErrorState error={resource.error} onRetry={resource.reload} context={`Could not load ${label}`} />;
  return <>{children(resource.data)}</>;
}

export function Mono({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <code className={`font-mono text-[0.8rem] text-muted ${className}`}>{children}</code>;
}

export function Time({ iso }: { iso: string | null | undefined }) {
  if (!iso) return <span className="text-faint">—</span>;
  return <time dateTime={iso} title={formatTime(iso)} className="whitespace-nowrap">{relativeTime(iso)}</time>;
}

export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="flex flex-col gap-1 text-sm">
      <span className="text-muted">{label}</span>
      {children}
      {hint && <span className="text-xs text-faint">{hint}</span>}
    </label>
  );
}

export const inputClass = 'rounded-md border border-line bg-bg px-2.5 py-1.5 text-sm text-ink placeholder:text-faint focus:border-accent focus:outline-none';

export function Stat({ label, value, hint }: { label: string; value: ReactNode; hint?: string }) {
  return (
    <div className="rounded-md border border-line bg-panel-2 px-3 py-2">
      <p className="text-xs uppercase tracking-wider text-faint">{label}</p>
      <p className="mt-0.5 text-lg font-semibold text-ink">{value}</p>
      {hint && <p className="text-xs text-muted">{hint}</p>}
    </div>
  );
}

export function Crumbs({ items }: { items: Array<{ href?: string; label: string }> }) {
  return (
    <nav aria-label="Breadcrumb" className="mb-3 text-sm text-muted">
      <ol className="flex flex-wrap items-center gap-1">
        {items.map((it, i) => (
          <li key={i} className="flex items-center gap-1">
            {i > 0 && <span aria-hidden="true" className="text-faint">/</span>}
            {it.href ? <Link className="hover:text-accent" href={it.href}>{it.label}</Link> : <span className="text-ink">{it.label}</span>}
          </li>
        ))}
      </ol>
    </nav>
  );
}

export function PageTitle({ title, subtitle, actions }: { title: ReactNode; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-xl font-semibold text-ink">{title}</h1>
        {subtitle && <div className="mt-1 text-sm text-muted">{subtitle}</div>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}
