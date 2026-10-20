import Link from 'next/link';
import { LogoMark } from '@/components/brand';

const GROUPS = [
  { title: 'Explore', links: [['The process', '#how'], ['Defense Lab', '/lab'], ['Pricing', '/pricing']] },
  { title: 'Build with Ari', links: [['Your projects', '/projects'], ['Connect a repository', '/connect'], ['Source code', 'https://github.com/adamissac/ari-ai']] },
] as const;

export function LandingFooter() {
  return (
    <footer className="landing-footer" data-testid="landing-footer">
      <div className="footer-ruler" aria-hidden="true" />
      <div className="footer-top">
        <Link href="/" aria-label="Back to Ari home" className="footer-ant"><LogoMark size={48} decorative /></Link>
        <div className="footer-directory">
          <span className="footer-wordmark ari-wordmark-text" aria-label="ARI">ARI<span aria-hidden="true">↗</span></span>
          <nav aria-label="Footer" className="footer-links">
            {GROUPS.map(group => <div key={group.title}><h2>{group.title}</h2>{group.links.map(([label, href]) => <Link key={label} href={href}>{label}<span aria-hidden="true">↗</span></Link>)}</div>)}
          </nav>
        </div>
      </div>
      <div className="footer-horizon" aria-hidden="true"><div /><div /></div>
      <div className="footer-bottom">
        <p>Software moves fast.<br />Proof should keep up.</p>
        <div><span className="footer-status"><i aria-hidden="true" /> Made for the next change.</span><span>© {new Date().getUTCFullYear()} ARI</span></div>
        <a href="#main" className="footer-top-link">Back to top <span aria-hidden="true">↑</span></a>
      </div>
    </footer>
  );
}
