'use client';

import Link from 'next/link';
import { useState, type FormEvent } from 'react';
import { api } from '@/lib/api';
import { useResource } from '@/lib/use-resource';
import { CREATE_PROJECT_NOTE } from '@/lib/create-project';
import { Async, Button, Empty, ErrorState, Field, inputClass, PageTitle, Panel, Time } from '@/components/ui';

export default function ProjectsPage() {
  const projects = useResource('projects', signal => api().projects({ signal }));
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const create = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api().createProject({ name: name.trim(), org_id: null, settings: null });
      setName('');
      projects.reload();
    } catch (err) { setError(err); } finally { setBusy(false); }
  };

  return (
    <>
      <PageTitle title="Projects" subtitle="Each project links repositories, authorized test scopes, assessments and monitoring history." />
      <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
        <Panel title="Your projects">
          <Async resource={projects} label="projects">
            {page => page.items.length === 0 ? <Empty>No projects yet. Create one to connect a repository.</Empty> : (
              <ul className="divide-y divide-line">
                {page.items.map(p => (
                  <li key={p.id} className="flex flex-wrap items-center justify-between gap-2 py-2.5">
                    <Link href={`/projects/${p.id}`} className="font-medium text-ink hover:text-accent">{p.name}</Link>
                    <span className="text-xs text-muted">created <Time iso={p.created_at} /> · monitoring {p.settings.monitoring_policy.enabled ? 'enabled' : 'disabled'}</span>
                  </li>
                ))}
              </ul>
            )}
          </Async>
        </Panel>
        <Panel title="New project">
          <p className="mb-3 text-sm text-muted" data-testid="create-project-note">{CREATE_PROJECT_NOTE}</p>
          <form onSubmit={create} className="flex flex-col gap-3">
            <Field label="Name"><input className={inputClass} value={name} onChange={e => setName(e.target.value)} required maxLength={200} name="project_name" /></Field>
            <Button type="submit" variant="primary" disabled={busy || !name.trim()}>Create project</Button>
            {error !== null && <ErrorState error={error} context="Create failed" />}
          </form>
        </Panel>
      </div>
    </>
  );
}
