'use client';

import type { Project, Repository } from '@hackatl/frontend-transport';
import Link from 'next/link';
import { useParams, usePathname } from 'next/navigation';
import { createContext, useContext, type ReactNode } from 'react';
import { api } from '@/lib/api';
import { useResource } from '@/lib/use-resource';
import { Crumbs, ErrorState, Loading } from '@/components/ui';

interface ProjectValue { project: Project; repos: Repository[]; reloadRepos: () => void; reloadProject: () => void }
const ProjectContext = createContext<ProjectValue | null>(null);

export function useProject(): ProjectValue {
  const value = useContext(ProjectContext);
  if (!value) throw new Error('useProject outside ProjectShell');
  return value;
}

/** Route params are untrusted strings; the transport rejects non-ID characters. */
export function useParam(name: string): string {
  const params = useParams();
  const value = params[name];
  return typeof value === 'string' ? value : '';
}

const TABS = [
  { href: '', label: 'Overview' },
  { href: '/scopes', label: 'Scopes' },
  { href: '/expectations', label: 'Expectations' },
  { href: '/findings', label: 'Findings' },
  { href: '/approvals', label: 'Approvals' },
  { href: '/monitoring', label: 'Monitoring' },
  { href: '/incidents', label: 'Incidents' },
  { href: '/settings', label: 'Settings' },
];

export function ProjectShell({ children }: { children: ReactNode }) {
  const id = useParam('projectId');
  const pathname = usePathname();
  const project = useResource(`project:${id}`, signal => api().project(id, { signal }));
  const repos = useResource(`repos:${id}`, signal => api().repositories(id, { signal }));
  if (project.status === 'loading' || repos.status === 'loading') return <Loading label="Loading project" />;
  if (project.status === 'error') return <ErrorState error={project.error} onRetry={project.reload} context="Could not load project" />;
  if (repos.status === 'error') return <ErrorState error={repos.error} onRetry={repos.reload} context="Could not load repositories" />;
  const base = `/projects/${project.data.id}`;
  return (
    <ProjectContext.Provider value={{ project: project.data, repos: repos.data.items, reloadRepos: repos.reload, reloadProject: project.reload }}>
      <Crumbs items={[{ href: '/projects', label: 'Projects' }, { href: base, label: project.data.name }]} />
      <header className="hero-ink project-head mb-3 rounded-2xl px-6 py-8 md:px-8 shadow-lg">
        <p className="label-mono text-white/60">Project</p>
        <p className="display mt-2 text-3xl font-semibold md:text-4xl" data-testid="project-title">{project.data.name}</p>
        <p className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-white/70">
          {repos.data.items.length === 0
            ? <span>No repository connected</span>
            : repos.data.items.map(r => <span key={r.id} className="font-mono text-xs text-white/85">{r.full_name}<span className="text-white/50"> · {r.default_branch}</span></span>)}
          <span className="flex items-center gap-1.5">
            <span aria-hidden="true" className={project.data.settings.monitoring_policy.enabled ? 'hero-ping' : 'inline-block h-1.5 w-1.5 rounded-full bg-white/40'} />
            Monitoring {project.data.settings.monitoring_policy.enabled ? 'on' : 'off'}
          </span>
        </p>
      </header>
      <nav aria-label="Project" className="project-tabs mb-8">
        {TABS.map(t => {
          const href = base + t.href;
          const active = t.href === '' ? pathname === base : pathname.startsWith(href);
          return (
            <Link key={t.label} href={href} aria-current={active ? 'page' : undefined} className="project-tab label-mono">
              {t.label}
            </Link>
          );
        })}
      </nav>
      {children}
    </ProjectContext.Provider>
  );
}
