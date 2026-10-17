'use client';

import Link from 'next/link';
import { useState, type FormEvent } from 'react';
import { api } from '@/lib/api';
import { useResource } from '@/lib/use-resource';
import { Async, Button, Empty, ErrorState, Field, inputClass, PageTitle, Panel, Time } from '@/components/ui';

const PILLARS = [
  { n: '1', title: 'Does it work as intended?', body: 'The Reviewer agent builds intent evidence from specs, tests and the change, then reproduces functional defects with executed tests.' },
  { n: '2', title: 'Can an attacker exploit it?', body: 'Seven separate security agents — Scout, Probe, Trace, Diagnose, Patch, Verify, Fortify — investigate inside an approved sandbox scope.' },
  { n: '3', title: 'Does it stay secure?', body: 'Signed GitHub events trigger durable re-assessment. A Double DQN policy trained in simulation offers labelled decision support.' },
];
const LOOP = ['Understand', 'Review', 'Attack safely', 'Diagnose', 'Repair', 'Verify', 'Monitor'];

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
      <div className="mb-6 grid gap-3 md:grid-cols-3">
        {PILLARS.map(p => (
          <div key={p.n} className="rounded-lg border border-line bg-panel p-4">
            <p className="text-xs font-semibold uppercase tracking-wider text-accent">Pillar {p.n}</p>
            <p className="mt-1 font-semibold">{p.title}</p>
            <p className="mt-1 text-sm text-muted">{p.body}</p>
          </div>
        ))}
      </div>
      <ol aria-label="Assessment loop" className="mb-6 flex flex-wrap items-center gap-1 text-xs text-muted">
        {LOOP.map((step, i) => (
          <li key={step} className="flex items-center gap-1">
            {i > 0 && <span aria-hidden="true" className="text-faint">→</span>}
            <span className="rounded border border-line bg-panel-2 px-2 py-0.5">{step}</span>
          </li>
        ))}
      </ol>
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
