import Image from 'next/image';

/** Product identity and the owner-supplied ant mark. The original PNG is preserved. */
export const BRAND_NAME = 'Ari AI';
export const BRAND_HEADLINE = 'Every change understood.';
export const BRAND_HEADLINE_REST = 'A fix counts only when independent tests agree.';
export const BRAND_TAGLINE = 'A repair counts only when independent, executed tests agree.';

export const LOGO_SRC = '/brand/ari-ant.png';

export function LogoMark({ size = 24, className = '', decorative = false, priority = false }: { size?: number; className?: string; decorative?: boolean; priority?: boolean }) {
  return (
    <span
      aria-hidden={decorative || undefined}
      data-testid="ari-logo"
      style={{ width: size, height: size }}
      className={`relative inline-block shrink-0 overflow-hidden rounded-md ${className}`}
    >
      {/* Crop only the wide paper margins in layout; preserve the supplied PNG and ant. */}
      <Image src={LOGO_SRC} alt={decorative ? '' : `${BRAND_NAME} logo`} width={size} height={size} sizes={`${size * 2}px`} preload={priority} className="object-cover scale-[1.6]" />
    </span>
  );
}

export function Wordmark({ className = '', priority = false }: { className?: string; priority?: boolean }) {
  return (
    <span className={`ari-wordmark flex items-center gap-2 ${className}`}>
      <LogoMark decorative priority={priority} />
      <span className="font-semibold uppercase tracking-[0.08em]">{BRAND_NAME}</span>
    </span>
  );
}
