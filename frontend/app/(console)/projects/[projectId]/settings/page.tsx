'use client';

import type { Project } from '@hackatl/frontend-transport';
import { useState, type FormEvent } from 'react';
import { useProject } from '@/components/project';
import { Button, ErrorState, Field, inputClass, Panel } from '@/components/ui';
import { api } from '@/lib/api';
import { draftOf, parseSettings, type Draft } from '@/lib/settings';

export default function SettingsPage() {
  const { project } = useProject();
  const [saved, setSaved] = useState<Project>(project);
  const [draft, setDraft] = useState<Draft>(() => draftOf(project));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [message, setMessage] = useState<string | null>(null);
  const set = <K extends keyof Draft>(k: K) => (v: Draft[K]) => setDraft(d => ({ ...d, [k]: v }));
  const dirty = JSON.stringify(draft) !== JSON.stringify(draftOf(saved));
  const parsed = parseSettings(draft);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if ('error' in parsed) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const next = await api().updateProject(saved.id, { name: draft.name.trim(), settings: parsed.settings });
      setSaved(next);
      setDraft(draftOf(next));
      setMessage('Saved. New assessments and monitoring decisions use these settings; running assessments keep the budget they started with.');
    } catch (err) { setError(err); } finally { setBusy(false); }
  };

  return (
    <form onSubmit={submit} className="grid grid-cols-1 gap-4 lg:grid-cols-2" aria-label="Project settings">
      <Panel title="Project">
        <Field label="Name"><input className={inputClass} value={draft.name} onChange={e => set('name')(e.target.value)} maxLength={200} /></Field>
        <div className="mt-3">
          <Field label="Languages" hint="Comma-separated. Code intelligence currently indexes Python.">
            <input className={inputClass} value={draft.languages} onChange={e => set('languages')(e.target.value)} />
          </Field>
        </div>
      </Panel>
      <Panel title="Default assessment budget">
        <p className="mb-3 text-sm text-muted">Hard ceilings enforced by the orchestrator. An assessment that reaches any limit stops and is marked budget-exhausted, never silently extended.</p>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <Field label="Max tokens"><input className={inputClass} inputMode="numeric" value={draft.maxTokens} onChange={e => set('maxTokens')(e.target.value)} /></Field>
          <Field label="Max USD"><input className={inputClass} inputMode="decimal" value={draft.maxUsd} onChange={e => set('maxUsd')(e.target.value)} /></Field>
          <Field label="Wall clock (s)"><input className={inputClass} inputMode="numeric" value={draft.maxWall} onChange={e => set('maxWall')(e.target.value)} /></Field>
        </div>
      </Panel>
      <Panel title="Continuous monitoring trigger policy" className="lg:col-span-2">
        <p className="mb-3 text-sm text-muted">
          Controls whether a pushed commit starts a targeted reassessment. Reassessments still require an active, approved scope;
          without one the event is recorded as blocked rather than tested.
        </p>
        <label className="mb-3 flex items-center gap-2 text-sm">
          <input type="checkbox" checked={draft.enabled} onChange={e => set('enabled')(e.target.checked)} />
          Start reassessments automatically on relevant changes
        </label>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Field label="Minimum interval between reassessments (s)" hint="Changes inside this window are coalesced.">
            <input className={inputClass} inputMode="numeric" value={draft.interval} onChange={e => set('interval')(e.target.value)} />
          </Field>
          <Field label="Record-only path globs" hint="One per line. If every changed path matches, the event is recorded without an assessment.">
            <textarea className={`${inputClass} min-h-24 font-mono`} value={draft.ignore} onChange={e => set('ignore')(e.target.value)} />
          </Field>
        </div>
        <p className="mb-2 mt-4 text-sm text-muted">Budget for each monitoring-triggered reassessment (separate from manual assessments).</p>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <Field label="Max tokens"><input className={inputClass} inputMode="numeric" value={draft.monTokens} onChange={e => set('monTokens')(e.target.value)} /></Field>
          <Field label="Max USD"><input className={inputClass} inputMode="decimal" value={draft.monUsd} onChange={e => set('monUsd')(e.target.value)} /></Field>
          <Field label="Wall clock (s)"><input className={inputClass} inputMode="numeric" value={draft.monWall} onChange={e => set('monWall')(e.target.value)} /></Field>
        </div>
      </Panel>
      <div className="flex flex-wrap items-center gap-3 lg:col-span-2">
        <Button type="submit" variant="primary" disabled={busy || !dirty || 'error' in parsed}>Save settings</Button>
        <Button type="button" disabled={busy || !dirty} onClick={() => setDraft(draftOf(saved))}>Discard changes</Button>
        {'error' in parsed && <span role="alert" className="text-sm text-bad">{parsed.error}</span>}
        {message && <span role="status" className="text-sm text-muted">{message}</span>}
      </div>
      {error !== null && <div className="lg:col-span-2"><ErrorState error={error} context="Settings not saved (only project owners can change settings)" /></div>}
    </form>
  );
}
