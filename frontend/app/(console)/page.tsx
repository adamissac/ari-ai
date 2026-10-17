'use client';

import Link from 'next/link';
import { useState, type FormEvent } from 'react';
import { api } from '@/lib/api';
import { useResource } from '@/lib/use-resource';
import { BRAND_HEADLINE, BRAND_HEADLINE_REST, BRAND_NAME } from '@/components/brand';
import { CREATE_PROJECT_NOTE } from '@/lib/create-project';
import { Reveal } from '@/components/reveal';
import { Async, Button, Empty, ErrorState, Field, inputClass, PageTitle, Panel, Time } from '@/components/ui';

const PILLARS = [
  { n: '01', title: 'Does it work as intended?', body: 'The Reviewer agent builds intent evidence from specs, tests and the change, then reproduces functional defects with executed tests.' },
  { n: '02', title: 'Can an attacker exploit it?', body: 'Seven separate security agents — Scout, Probe, Trace, Diagnose, Patch, Verify, Fortify — investigate inside an approved sandbox scope.' },
  { n: '03', title: 'Does it stay secure?', body: 'Signed GitHub events trigger durable re-assessment. A Double DQN policy trained in simulation offers labelled decision support.' },
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
      <section className="hero-ink -mx-4 mb-8 rounded-none px-6 py-14 sm:mx-0 sm:rounded-2xl md:px-12 md:py-20" aria-labelledby="hero-title">
        <p className="label-mono text-white/70">{BRAND_NAME} · software assurance</p>
        <h1 id="hero-title" className="display mt-4 max-w-4xl text-4xl font-medium md:text-6xl">
          {BRAND_HEADLINE}<br /><span className="text-white/70">{BRAND_HEADLINE_REST}</span>
        </h1>
        <p className="mt-5 max-w-2xl text-sm text-white/75 md:text-base">
          {BRAND_NAME} learns what your software is supposed to do, tests it like an attacker inside an approved sandbox,
          and only calls a repair done when independent, executed tests agree.
        </p>
        <ol aria-label="Assessment loop" className="mt-8 flex flex-wrap gap-1.5">
          {LOOP.map((step, i) => (
            <li key={step} className="label-mono flex items-center gap-1.5 rounded-md bg-white/10 px-2.5 py-1 text-white/85 backdrop-blur transition-colors duration-[250ms] hover:bg-white/20">
              <span className="text-white/50">{String(i + 1).padStart(2, '0')}</span>{step}
            </li>
          ))}
        </ol>
      </section>
      <div className="mb-8 grid gap-3 md:grid-cols-3">
        {PILLARS.map((p, i) => (
          <Reveal key={p.n} delay={i * 90}>
            <div className="group h-full rounded-xl border border-line bg-panel p-5 transition-[border-color,box-shadow,transform] duration-300 hover:-translate-y-0.5 hover:border-brand/40 hover:shadow-[0_12px_28px_-16px_rgba(194,69,45,0.45)]">
              <p className="label-mono text-brand">{p.n}</p>
              <p className="mt-3 text-lg font-semibold tracking-tight">{p.title}</p>
              <p className="mt-2 text-sm text-muted">{p.body}</p>
            </div>
          </Reveal>
        ))}
      </div>
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
