import type { CSSProperties } from 'react';
import Link from 'next/link';
import { Reveal } from '@/components/reveal';
import { LogoMark } from '@/components/brand';
import { AGENTS } from '@/lib/status';

const CREW = AGENTS.filter(a => a.name !== 'reviewer');

const GROUPS = [
  { title: 'Explore', links: [['The process', '#how'], ['Defense Lab', '/lab'], ['Pricing', '/pricing']] },
  { title: 'Build with Ari', links: [['Your projects', '/projects'], ['Connect a repository', '/connect'], ['Source code', 'https://github.com/adamissac/ari-ai']] },
] as const;

export function LandingFooter() {
  return (
    <footer className="landing-footer" data-testid="landing-footer">
      <div aria-hidden="true" className="footer-glow" />
      <Reveal className="footer-crew">
        <p className="footer-crew-tag">Seven agents · one shared brain · every change</p>
        <ol aria-label="The seven agents" className="footer-crew-track">
          {CREW.map((a, n) => (
            <li key={a.name} data-team={a.team} style={{ '--n': n } as CSSProperties}>
              <span className="footer-crew-name">{a.label}</span>
              <span className="footer-crew-team">{a.team === 'Independent' ? 'Independent' : `${a.team} team`}</span>
            </li>
          ))}
        </ol>
      </Reveal>
      <Reveal className="footer-top">
        <div className="footer-identity">
          <Link href="/" aria-label="Back to Ari home" className="footer-brand"><LogoMark size={36} decorative /><span className="ari-wordmark-text">ARI</span></Link>
          <p>Software moves fast.<br />Proof should keep up.</p>
        </div>
        <nav aria-label="Footer" className="footer-links">
          {GROUPS.map(group => <div key={group.title}><h2>{group.title}</h2>{group.links.map(([label, href]) => <Link key={label} href={href}>{label}</Link>)}</div>)}
        </nav>
      </Reveal>
      <Reveal className="footer-bottom" delay={100}>
        <span>© {new Date().getUTCFullYear()} ARI</span>
        <a href="#main" className="footer-top-link">Back to top <span aria-hidden="true">↑</span></a>
      </Reveal>
      <div aria-hidden="true" className="footer-word">ARI</div>
    </footer>
  );
}
