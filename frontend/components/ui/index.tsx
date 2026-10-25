'use client';

import Link from 'next/link';
import { cloneElement, isValidElement, useId, type ButtonHTMLAttributes, type ReactElement, type ReactNode } from 'react';
import { describeError } from '@/lib/api';
import type { Resource } from '@/lib/use-resource';
import type { StatusView, Tone } from '@/lib/status';
import { formatTime, relativeTime } from '@/lib/format';
import { useRevealOnScroll } from '@/components/reveal';

const TONE: Record<Tone, string> = {
  ok: 'border-ok/50 text-ok',
  warn: 'border-warn/50 text-warn',
  bad: 'border-bad/50 text-bad',
  info: 'border-info/50 text-info',
  accent: 'border-accent/50 text-accent',
  neutral: 'border-line-2 text-muted',
};

export function Badge({ view, title }: { view: StatusView; title?: string }) {
  const mark = view.glyph === '⏸' ? 'paused' : view.tone === 'bad' ? 'failed' : view.tone === 'ok' ? 'done' : 'pending';
  return (
    <span title={title} className={`status-badge inline-flex items-center gap-1 whitespace-nowrap rounded-[var(--radius-1)] border bg-transparent px-2 py-0.5 font-mono text-[10px] font-medium uppercase tracking-[0.06em] ${TONE[view.tone]}`}>
      <span aria-hidden="true" className={`status-mark status-mark-${mark}`}>{mark === 'failed' ? '×' : null}</span>
||||||| 1fbc62a3
    <span title={title} className={`status-badge inline-flex items-center gap-1 whitespace-nowrap rounded-full border px-2 py-0.5 text-xs font-medium ${TONE[view.tone]}`}>
      <span aria-hidden="true">{view.glyph}</span>
      {view.label}
    </span>
  );
}

export function Tag({ children, tone = 'neutral' }: { children: ReactNode; tone?: Tone }) {
  return <span className={`inline-flex items-center rounded-[var(--radius-1)] border bg-transparent px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.06em] ${TONE[tone]}`}>{children}</span>;
}

export function Panel({ title, actions, children, className = '', id }: { title?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string; id?: string }) {
  const ref = useRevealOnScroll<HTMLElement>();
  return (
    <section ref={ref} id={id} className={`panel rounded-[var(--radius-3)] border border-line bg-panel ${className}`} aria-label={typeof title === 'string' ? title : undefined}>
      {(title || actions) && (
        <header className="flex flex-wrap items-center justify-between gap-2 border-b border-line bg-panel-2/60 px-4 py-2.5">
          {title && <h2 className="label-mono flex items-center gap-2 text-ink"><span aria-hidden="true" className="h-3 w-0.5 rounded-full bg-brand" />{title}</h2>}
          {actions && <div className="flex min-w-0 max-w-full flex-wrap items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className="p-5">{children}</div>
    </section>
  );
}

export function Button({ variant = 'secondary', className = '', children, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'danger' | 'ghost' }) {
  const styles = {
    primary: 'border border-transparent bg-brand text-on-brand hover:bg-brand-deep',
    secondary: 'border border-line-2 bg-transparent text-ink hover:bg-panel-2',
    danger: 'border border-bad/50 bg-transparent text-bad hover:bg-bad/10',
    ghost: 'border border-transparent bg-transparent text-muted hover:bg-panel-2 hover:text-ink',
  }[variant];
  return (
    <button
      type="button"
      data-variant={variant}
      {...props}
      className={`btn inline-flex h-8 items-center justify-center gap-1.5 rounded-[var(--radius-2)] px-3 font-sans text-xs font-medium transition-colors duration-[120ms] ease-[var(--ease-out)] disabled:cursor-not-allowed disabled:opacity-50 ${styles} ${className}`}
    >
      {typeof children === 'string' ? <RollText>{children}</RollText> : children}
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
  return (
    <div role="alert" data-testid="error-state" className="rounded-[var(--radius-3)] border border-bad/40 bg-transparent p-3 text-sm">
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
  return <p className="empty-state rounded-[var(--radius-3)] border border-line bg-panel px-4 py-3 text-center text-sm text-muted">{children}</p>;
}

export function Loading({ label = 'Loading' }: { label?: string }) {
  return <p role="status" aria-live="polite" className="text-sm text-muted"><span aria-hidden="true" className="loading-dot" />{label}…</p>;
}

/** Render loading / error / ready for a resource with no silent fallbacks. */
export function Async<T>({ resource, label, children }: { resource: Resource<T>; label: string; children: (data: T) => ReactNode }) {
  if (resource.status === 'loading') return <Loading label={`Loading ${label}`} />;
  if (resource.status === 'error') return <ErrorState error={resource.error} onRetry={resource.reload} context={`Could not load ${label}`} />;
  return <>{children(resource.data)}</>;
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

export const inputClass = 'max-w-full rounded-[var(--radius-2)] border border-line-2 bg-bg px-2.5 py-1.5 text-sm text-ink placeholder:text-faint transition-colors duration-[120ms] focus:border-brand focus:outline-none';

export function Stat({ label, value, hint }: { label: string; value: ReactNode; hint?: string }) {
  return (
    <div className="rounded-[var(--radius-3)] border border-line bg-panel px-4 py-3.5">
      <p className="label-mono text-faint">{label}</p>
      <p className="mt-2 font-display text-2xl font-semibold tabular-nums tracking-tight text-ink">{value}</p>
      {hint && <p className="text-xs text-muted">{hint}</p>}
    </div>
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

export function PageTitle({ title, subtitle, actions, eyebrow }: { title: ReactNode; subtitle?: ReactNode; actions?: ReactNode; eyebrow?: ReactNode }) {
  return (
    <div className="page-title mb-6 flex flex-wrap items-end justify-between gap-3 border-b border-line pb-5">
      <div className="min-w-0">
        {eyebrow && <p className="label-mono mb-2 text-brand">{eyebrow}</p>}
        <h1 className="text-3xl font-semibold tracking-[-0.03em] text-ink md:text-4xl">{title}</h1>
        {subtitle && <div className="mt-2 max-w-2xl text-sm text-muted">{subtitle}</div>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}
