/** Product identity. The logo is a PLACEHOLDER until the real mark is designed. */
export const BRAND_NAME = 'Ari AI';
export const BRAND_HEADLINE = 'Every change understood.';
export const BRAND_HEADLINE_REST = 'A fix counts only when independent tests agree.';
export const BRAND_TAGLINE = 'A repair counts only when independent, executed tests agree.';

export function LogoPlaceholder({ size = 24, className = '' }: { size?: number; className?: string }) {
  return (
    <span
      role="img"
      aria-label={`${BRAND_NAME} logo (placeholder)`}
      data-testid="logo-placeholder"
      title="Logo placeholder"
      style={{ width: size, height: size }}
      className={`grid shrink-0 place-items-center rounded-md border border-dashed border-brand/60 bg-brand text-[0.6rem] font-bold leading-none text-on-brand ${className}`}
    >
      A
    </span>
  );
}

export function Wordmark({ className = '' }: { className?: string }) {
  return (
    <span className={`flex items-center gap-2 ${className}`}>
      <LogoPlaceholder />
      <span className="font-semibold uppercase tracking-[0.08em]">{BRAND_NAME}</span>
    </span>
  );
}
