import Link from 'next/link';
import { Button } from '@/components/ui';

const WORKSPACE_LINKS = [
  ['Analytics', '', 'Analytics summarizes saved checks and findings for the selected repository.'],
  ['Commits', '/commits', 'Commits shows repository history, reviews, and recorded agent work.'],
  ['Findings', '/findings', 'Findings lists issues from this repository’s saved assessments.'],
  ['Approvals', '/approvals', 'Approvals is where pending decisions are reviewed.'],
  ['Settings', '/settings', 'Settings keeps project and repository controls together.'],
] as const;

export function SetupDone({ projectId, repoId, onBack }: { projectId: string; repoId: string; onBack: () => void }) {
  const base = `/projects/${projectId}`;
  const repoQuery = `repo=${encodeURIComponent(repoId)}`;

  return (
    <section data-testid="setup-done" className="rounded-xl border border-line bg-panel p-5 sm:p-6">
      <p className="label-mono text-ok">Setup complete</p>
      <h2 className="mt-1 text-xl font-semibold tracking-tight">You&apos;re set up</h2>
      <p className="mt-1 text-sm text-muted">Here&apos;s where everything lives.</p>
      <div className="mt-5 divide-y divide-line border-y border-line">
        {WORKSPACE_LINKS.map(([label, route, description]) => (
          <div key={label} className="py-3">
            <Link href={`${base}${route}?${repoQuery}`} className="font-semibold text-ink hover:text-brand">{label}</Link>
            <p className="mt-1 text-sm text-muted">{description}</p>
          </div>
        ))}
      </div>
      <div className="mt-5 flex flex-wrap items-center gap-3">
        <Link href={`${base}?${repoQuery}`} className="btn label-mono inline-flex h-8 items-center justify-center rounded-md bg-brand px-3 text-on-brand shadow-[0_6px_16px_-8px_rgba(194,69,45,0.6)] transition-[background-color,color,box-shadow,transform] duration-[250ms] hover:bg-brand-deep hover:shadow-[0_8px_20px_-8px_rgba(194,69,45,0.5)] active:scale-[0.97]">Go to Analytics</Link>
        <Button onClick={onBack}>Back to setup</Button>
      </div>
    </section>
  );
}
