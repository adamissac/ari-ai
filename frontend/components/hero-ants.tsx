import type { CSSProperties } from 'react';
import s from './hero-ants.module.css';

type Load = 'hammer' | 'code' | 'brace' | 'bolt';

const WALKERS: { load: Load; delay: number }[] = [
  { load: 'code', delay: 0 },
  { load: 'hammer', delay: -11 },
];

const LINES = [62, 44, 78, 50];

function Ant({ className = '' }: { className?: string }) {
  return <span className={`${s.ant} ${className}`} />;
}

function Item({ load }: { load: Load }) {
  if (load === 'hammer') return <span className={s.hammer}><span className={s.hammerHead} /></span>;
  if (load === 'bolt') return <span className={s.bolt} />;
  return <span className={s.chip}>{load === 'brace' ? '{ }' : '</>'}</span>;
}

/**
 * Decorative strip along the bottom of the hero: logo-shaped ants carry tiny hammers and code
 * pieces to a small computer on the right, where two builders hand pieces up and a program types
 * itself onto the screen. Purely visual (aria-hidden, no pointer events); hidden on small screens
 * and frozen under reduced motion.
 */
export function HeroAnts() {
  return (
    <div aria-hidden="true" className={s.scene} data-testid="hero-ants">
      <span className={s.ground} />
      {WALKERS.map((w, n) => (
        <span key={n} className={s.walker} style={{ animationDelay: `${w.delay}s` } as CSSProperties}>
          <span className={s.bob} style={{ animationDelay: `${n * -0.17}s` }}>
            <span className={s.load}><Item load={w.load} /></span>
            <Ant />
          </span>
        </span>
      ))}
      <div className={s.site}>
        <span className={s.builder}>
          <span className={s.swing}><span className={s.hammer}><span className={s.hammerHead} /></span></span>
          <Ant className={s.builderAnt} />
        </span>
        <div className={s.monitor}>
          <div className={s.screen}>
            {LINES.map((w, n) => (
              <span key={n} className={s.line} style={{ '--w': `${w}%`, '--n': n } as CSSProperties} />
            ))}
            <span className={s.caret} />
          </div>
          <span className={s.stand} />
        </div>
      </div>
    </div>
  );
}
