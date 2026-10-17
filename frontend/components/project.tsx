'use client';

import type { Project, Repository } from '@hackatl/frontend-transport';
import Link from 'next/link';
import { useParams, usePathname } from 'next/navigation';
import { createContext, useContext, type ReactNode } from 'react';
import { api } from '@/lib/api';
import { useResource } from '@/lib/use-resource';
import { Crumbs, ErrorState, Loading } from '@/components/ui';

interface ProjectValue { project: Project; repos: Repository[]; reloadRepos: () => void }
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
  { href: '/findings', label: 'Findings' },
  { href: '/approvals', label: 'Approvals' },
  { href: '/monitoring', label: 'Monitoring' },
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
    <ProjectContext.Provider value={{ project: project.data, repos: repos.data.items, reloadRepos: repos.reload }}>
      <Crumbs items={[{ href: '/', label: 'Projects' }, { href: base, label: project.data.name }]} />
      <nav aria-label="Project" className="mb-5 flex flex-wrap gap-1 border-b border-line">
        {TABS.map(t => {
          const href = base + t.href;
          const active = t.href === '' ? pathname === base : pathname.startsWith(href);
          return (
            <Link key={t.label} href={href} aria-current={active ? 'page' : undefined}
              className={`-mb-px border-b-2 px-3 py-2 text-sm ${active ? 'border-accent text-ink' : 'border-transparent text-muted hover:text-ink'}`}>
              {t.label}
            </Link>
          );
        })}
      </nav>
      {children}
    </ProjectContext.Provider>
  );
}
