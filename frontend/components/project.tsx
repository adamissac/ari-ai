'use client';

import type { Project, Repository } from '@hackatl/frontend-transport';
import Link from 'next/link';
import { useParams, usePathname, useRouter } from 'next/navigation';
import { createContext, useContext, useEffect, useState, useSyncExternalStore, type ReactNode } from 'react';
import { useSelectedRepo } from '@/lib/selected-repo';
import { api } from '@/lib/api';
import { useResource } from '@/lib/use-resource';
import { AutomationStatus } from '@/components/automation-status';
import { ErrorState, Loading, Mono, inputClass } from '@/components/ui';
import { isLegacySetupEvidence, isSetupComplete, progressToServer, readLegacySetupProgress, SETUP_SAVED_EVENT } from '@/lib/setup-progress';

interface ProjectValue {
  project: Project;
  repos: Repository[];
  selectedRepo: Repository | null;
  selectRepo: (id: string) => void;
  reloadRepos: () => void;
  reloadProject: () => void;
}
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
  { href: '', label: 'Analytics', icon: 'analytics' },
  { href: '/commits', label: 'Commits', icon: 'commits' },
  { href: '/findings', label: 'Findings', icon: 'findings' },
  { href: '/approvals', label: 'Approvals', icon: 'approvals' },
  { href: '/settings', label: 'Settings', icon: 'settings' },
] as const;

const MORE = [
  { href: '/live-defense', label: 'Live Defense' },
  { href: '/incidents', label: 'Incidents' },
  { href: '/monitoring', label: 'Monitoring' },
  { href: '/scopes', label: 'Authorized scopes' },
  { href: '/expectations', label: 'Expectations' },
  { href: '/simulate', label: 'Simulate' },
  { href: '/onboarding', label: 'Onboarding' },
  { href: '/setup', label: 'Setup' },
] as const;

type NavIconName = typeof TABS[number]['icon'] | 'more';

function NavIcon({ name }: { name: NavIconName }) {
  const shapes: Record<NavIconName, ReactNode> = {
    analytics: <><rect x="3" y="3" width="18" height="18" rx="2" /><path d="M7 16v2m5-7v7m5-11v11" /></>,
    commits: <><circle cx="6" cy="12" r="2" /><circle cx="18" cy="6" r="2" /><circle cx="18" cy="18" r="2" /><path d="M8 12h4a4 4 0 0 0 4-4V8m-8 4h4a4 4 0 0 1 4 4v0" /></>,
    findings: <><circle cx="10.5" cy="10.5" r="6.5" /><path d="m16 16 5 5" /></>,
    approvals: <><path d="m5 12 4 4L19 6" /><path d="M4 4v4m16 8v4" /></>,
    settings: <><circle cx="12" cy="12" r="3" /><path d="m19.4 15 .1.1 1.4 1.1-1.4 2.4-1.7-.7a8 8 0 0 1-1.7 1l-.3 1.8h-2.8l-.3-1.8a8 8 0 0 1-1.7-1l-1.7.7-1.4-2.4 1.4-1.1a8 8 0 0 1 0-2l-1.4-1.1 1.4-2.4 1.7.7a8 8 0 0 1 1.7-1l.3-1.8h2.8l.3 1.8a8 8 0 0 1 1.7 1l1.7-.7 1.4 2.4-1.4 1.1a8 8 0 0 1 0 2Z" /></>,
    more: <><circle cx="5" cy="12" r="1" /><circle cx="12" cy="12" r="1" /><circle cx="19" cy="12" r="1" /></>,
  };
  return <svg aria-hidden="true" className="h-4 w-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">{shapes[name]}</svg>;
}

function LockIcon() {
  return <svg aria-hidden="true" className="project-lock-icon h-3 w-3 shrink-0" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round">
    <rect x="2.5" y="7" width="11" height="7" rx="1.5" />
    <path d="M5 7V4.8a3 3 0 0 1 6 0V7" />
  </svg>;
}
const matchesRoute = (pathname: string, base: string, route: string) =>
  pathname === `${base}${route}` || pathname.startsWith(`${base}${route}/`);

function routeHref(base: string, route: string, repoId: string | null) {
  const path = `${base}${route}`;
  return repoId ? `${path}?repo=${encodeURIComponent(repoId)}` : path;
}

export function ProjectNavigation({ base, repoId, locked = false }: { base: string; repoId: string | null; locked?: boolean }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const activeMore = MORE.find(item => matchesRoute(pathname, base, item.href));
  const commitsActive = matchesRoute(pathname, base, '/commits')
    || pathname.startsWith(`${base}/assessments/`);
  return (
    <nav aria-label="Project" className="project-tabbar">
      <div className="project-tab-scroll">
        {TABS.map(item => {
          const active = item.href === ''
            ? pathname === base
            : item.href === '/commits'
              ? commitsActive
              : matchesRoute(pathname, base, item.href);
          const disabled = locked;
          return (
            disabled ? (
              <span key={item.label} aria-disabled="true" title="Finish setup first" className="project-tab text-faint">
                <NavIcon name={item.icon} /><span className="project-tab-label">{item.label}</span><LockIcon />
              </span>
            ) : (
              <Link
                key={item.label}
                href={routeHref(base, item.href, repoId)}
                aria-current={active ? 'page' : undefined}
                data-coach={item.href === '' ? 'analytics' : item.href.slice(1)}
                className={`project-tab ${active ? 'is-active' : ''}`}
              >
                <NavIcon name={item.icon} /><span className="project-tab-label">{item.label}</span>
              </Link>
            )
          );
        })}
      </div>
      <div className="project-more">
        <button
          type="button"
          aria-controls="project-more-menu"
          aria-expanded={open}
          aria-current={activeMore ? 'page' : undefined}
          title={locked ? 'Finish setup first' : undefined}
          className={`project-tab project-more-button ${activeMore ? 'is-active' : ''}`}
          onClick={() => setOpen(value => !value)}
        >
          <NavIcon name="more" /><span className="project-tab-label">{activeMore?.label ?? 'More'}</span><span aria-hidden="true" className="project-more-chevron">{open ? '▴' : '▾'}</span>
        </button>
        <div id="project-more-menu" className="project-more-menu" hidden={!open}>
          {MORE.map(item => {
            const active = activeMore?.href === item.href;
            const firstRun = item.href === '/setup' || item.href === '/onboarding' || item.href === '/live-defense';
            if (locked && !firstRun) {
              return <span key={item.label} aria-disabled="true" title="Finish setup first" className="project-more-link text-faint">{item.label} <LockIcon /></span>;
            }
            return (
              <Link
                key={item.label}
                href={routeHref(base, item.href, repoId)}
                aria-current={active ? 'page' : undefined}
                data-coach={item.href === '/setup' ? 'setup' : undefined}
                className={`project-more-link ${active ? 'is-active' : ''}`}
                onClick={() => setOpen(false)}
              >
                {item.label}
              </Link>
            );
          })}
        </div>
      </div>
    </nav>
  );
}

export function ProjectShell({ children }: { children: ReactNode }) {
  const id = useParam('projectId');
  const base = `/projects/${id}`;
  const pathname = usePathname();
  const router = useRouter();
  const project = useResource(`project:${id}`, signal => api().project(id, { signal }));
  const repos = useResource(`repos:${id}`, signal => api().repositories(id, { signal }));
  const repoItems = repos.status === 'ready' ? repos.data.items : [];
  const { selectedRepo, selectRepo } = useSelectedRepo(id, repoItems);
  const selectedRepoId = selectedRepo?.id ?? null;
  const savedSetup = useResource(
    selectedRepoId ? `setup-state:${id}:${selectedRepoId}` : null,
    signal => api().repositorySetup(selectedRepoId!, { signal }),
  );
  const setupCheck = useResource(
    selectedRepoId ? `setup-check:${id}:${selectedRepoId}` : null,
    signal => hasLegacySetupEvidence(id, selectedRepoId!, signal),
  );
  const reloadSavedSetup = savedSetup.reload;
  useEffect(() => {
    window.addEventListener(SETUP_SAVED_EVENT, reloadSavedSetup);
    return () => window.removeEventListener(SETUP_SAVED_EVENT, reloadSavedSetup);
  }, [reloadSavedSetup]);
  // Browser-only completion from an earlier build still counts, and moves to the server.
  const legacyComplete = useSyncExternalStore(
    callback => {
      window.addEventListener(SETUP_SAVED_EVENT, callback);
      window.addEventListener('storage', callback);
      return () => {
        window.removeEventListener(SETUP_SAVED_EVENT, callback);
        window.removeEventListener('storage', callback);
      };
    },
    () => Boolean(selectedRepoId && readLegacySetupProgress(id, selectedRepoId)?.complete),
    () => false,
  );
  const serverComplete = savedSetup.status === 'ready' && savedSetup.data.complete;
  useEffect(() => {
    if (!selectedRepoId || !legacyComplete || savedSetup.status !== 'ready' || savedSetup.data.complete) return;
    api().saveRepositorySetup(selectedRepoId, progressToServer(readLegacySetupProgress(id, selectedRepoId) ?? { answers: {}, complete: true }))
      .then(reloadSavedSetup, () => { /* still complete in this browser */ });
  }, [id, legacyComplete, reloadSavedSetup, savedSetup, selectedRepoId]);
  const knownComplete = serverComplete || legacyComplete;
  const setupReady = (savedSetup.status !== 'loading' && setupCheck.status !== 'loading') || knownComplete;
  const complete = isSetupComplete({ answers: {}, complete: knownComplete }, setupCheck.status === 'ready' && setupCheck.data);
  const setupRoute = pathname === `${base}/setup` || pathname.startsWith(`${base}/setup/`);
  // First-run surfaces (onboarding checklist, live-defense connect) must stay
  // reachable before any assessment exists: they are how setup completes.
  const freeRoute = setupRoute
    || pathname === `${base}/onboarding` || pathname.startsWith(`${base}/onboarding/`)
    || pathname === `${base}/live-defense` || pathname.startsWith(`${base}/live-defense/`);
  // Only lock on a confirmed "not finished" from the server; a disconnected repo has no setup to finish.
  const locked = Boolean(selectedRepo && !selectedRepo.disconnected && setupReady && savedSetup.status === 'ready' && !complete);
  useEffect(() => {
    if (locked && !freeRoute && selectedRepo) {
      router.replace(`${base}/setup?repo=${encodeURIComponent(selectedRepo.id)}`);
    }
  }, [base, freeRoute, locked, router, selectedRepo]);

  if (project.status === 'loading' || repos.status === 'loading') return <Loading label="Loading project" />;
  if (project.status === 'error') return <ErrorState error={project.error} onRetry={project.reload} context="Could not load project" />;
  if (repos.status === 'error') return <ErrorState error={repos.error} onRetry={repos.reload} context="Could not load repositories" />;
  const monitoring = project.data.settings.monitoring_policy.enabled;
  const selected = selectedRepo ?? repoItems[0] ?? null;
  if (selectedRepo && !freeRoute && !setupReady) return <Loading label="Checking setup" />;
  if (locked && !freeRoute) return <Loading label="Opening setup" />;
  return (
    <ProjectContext.Provider value={{ project: project.data, repos: repoItems, selectedRepo, selectRepo, reloadRepos: repos.reload, reloadProject: project.reload }}>
      <div className="project-shell min-w-0">
        <header className="project-head flex min-w-0 flex-col gap-3 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex min-w-0 flex-wrap items-center gap-x-5 gap-y-2">
            <Link href="/connect" className="label-mono shrink-0 text-muted hover:text-ink">← Projects</Link>
            <p className="min-w-0 break-words font-display text-lg font-semibold tracking-tight" data-testid="project-title">{project.data.name}</p>
            {repoItems.length > 1
              ? <div className="min-w-0">
                <label htmlFor="project-repo-switcher" className="block text-xs text-muted">Repository</label>
                <span className="relative block">
                  <select
                    id="project-repo-switcher"
                    aria-label="Repository"
                    data-testid="repo-switcher"
                    data-coach="repo-switcher"
                    className={`${inputClass} min-w-0 max-w-full appearance-none border-line-2 pr-9 hover:border-brand`}
                    value={selectedRepo?.id ?? ''}
                    onChange={event => selectRepo(event.target.value)}
                  >
                    {repoItems.filter(repo => !repo.disconnected).map(repo => <option key={repo.id} value={repo.id}>{repo.full_name} · {repo.default_branch}</option>)}
                    {repoItems.some(repo => repo.disconnected) && (
                      <optgroup label="Disconnected (history only)">
                        {repoItems.filter(repo => repo.disconnected).map(repo => <option key={repo.id} value={repo.id}>{repo.full_name} · disconnected</option>)}
                      </optgroup>
                    )}
                  </select>
                  <svg aria-hidden="true" className="pointer-events-none absolute right-2 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="m7 10 5 5 5-5" /></svg>
                </span>
              </div>
              : repoItems.length === 1
                ? <span data-testid="repo-switcher" data-coach="repo-switcher" className="flex min-w-0 flex-wrap items-baseline gap-x-1 text-sm">
                  <Mono className="text-ink">{selected!.full_name}</Mono>
                  <span className="text-muted">· {selected!.default_branch}</span>
                  {selected!.disconnected && <span className="text-warn" data-testid="repo-disconnected">· Disconnected</span>}
                </span>
                : <span data-testid="repo-switcher" className="flex flex-wrap items-center gap-x-2 text-sm text-muted">
                  <span>No repository connected</span>
                  <Link className="text-brand hover:underline" href={`${base}/settings#connect-repo`}>Connect one</Link>
                </span>}
          </div>
          {selectedRepo
            ? <AutomationStatus repoId={selectedRepo.id} />
            : <span className="flex shrink-0 items-center gap-2 text-xs text-muted" aria-label={`Monitoring ${monitoring ? 'on' : 'off'}`}>
              <span aria-hidden="true" className={`h-2 w-2 rounded-full ${monitoring ? 'bg-ok' : 'bg-faint'}`} />
              Monitoring {monitoring ? 'on' : 'off'}
            </span>}
        </header>
        <ProjectNavigation base={base} repoId={selectedRepo?.id ?? null} locked={locked} />
        <div className="project-body min-w-0 pt-6">{children}</div>
      </div>
    </ProjectContext.Provider>
  );
}

async function hasLegacySetupEvidence(projectId: string, repoId: string, signal: AbortSignal): Promise<boolean> {
  let cursor: string | undefined;
  do {
    const page = await api().assessments(projectId, { repoId, ...(cursor ? { cursor } : {}), signal });
    if (page.items.some(isLegacySetupEvidence)) return true;
    cursor = page.next_cursor ?? undefined;
  } while (cursor);
  return false;
}
